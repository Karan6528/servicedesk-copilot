"""Local, explainable triage engine. No API key, no internet, no GPU.

Given a customer message (English or German) it returns:
- language      "en" / "de"
- category      one of CATEGORIES
- urgency       critical / high / normal / low
- confidence    0..1 (share of the winning category's keyword score)
- matched       which keywords decided it (so a human can see *why*)

It is deliberately simple: weighted keyword rules. That makes it fast,
testable and easy to explain in a review. An LLM can replace it via
app/llm.py, and the rule engine stays as the fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORIES = (
    "roadside_assistance",
    "workshop_repair",
    "charging_ev",
    "billing_invoice",
    "complaint",
    "general_inquiry",
)

CATEGORY_LABELS = {
    "roadside_assistance": "Roadside assistance",
    "workshop_repair": "Workshop / repair appointment",
    "charging_ev": "Charging & EV",
    "billing_invoice": "Billing / invoice",
    "complaint": "Complaint",
    "general_inquiry": "General inquiry",
}

# keyword -> weight. Lower-case. Stems are fine because we match substrings
# at word starts (see _hits).
KEYWORDS: dict[str, dict[str, float]] = {
    "roadside_assistance": {
        "breakdown": 3,
        "broke down": 3,
        "stranded": 3,
        "tow": 2,
        "flat tyre": 2,
        "flat tire": 2,
        "won't start": 2,
        "wont start": 2,
        "does not start": 2,
        "doesn't start": 2,
        "battery dead": 2,
        "highway": 1,
        "motorway": 1,
        "autobahn": 1,
        "stuck": 1,
        "panne": 3,
        "liegengeblieben": 3,
        "abschlepp": 2,
        "reifenpanne": 2,
        "springt nicht an": 2,
        "pannenhilfe": 3,
    },
    "workshop_repair": {
        "appointment": 2,
        "workshop": 2,
        "service": 1,
        "inspection": 2,
        "repair": 2,
        "noise": 2,
        "warning light": 2,
        "brake": 2,
        "oil": 1,
        "broken": 1,
        "defect": 2,
        "recall": 2,
        "termin": 2,
        "werkstatt": 2,
        "inspektion": 2,
        "reparatur": 2,
        "geräusch": 2,
        "warnleuchte": 2,
        "bremse": 2,
        "defekt": 2,
        "kaputt": 1,
        "rückruf": 2,
        "wartung": 2,
    },
    "charging_ev": {
        "charging": 3,
        "charge": 2,
        "charger": 2,
        "wallbox": 3,
        "cable": 1,
        "range": 2,
        "kwh": 2,
        "charging station": 3,
        "electric": 1,
        "laden": 2,
        "ladekabel": 3,
        "ladestation": 3,
        "ladesäule": 3,
        "reichweite": 2,
        "lädt": 2,
    },
    "billing_invoice": {
        "invoice": 3,
        "bill": 2,
        "charged twice": 3,
        "payment": 2,
        "refund": 3,
        "price": 1,
        "cost": 1,
        "receipt": 2,
        "overcharged": 3,
        "rechnung": 3,
        "zahlung": 2,
        "erstattung": 3,
        "rückerstattung": 3,
        "preis": 1,
        "kosten": 1,
        "doppelt abgebucht": 3,
        "gutschrift": 2,
    },
    "complaint": {
        "complaint": 3,
        "unacceptable": 3,
        "disappointed": 2,
        "angry": 2,
        "terrible": 2,
        "worst": 2,
        "rude": 2,
        "never again": 3,
        "lawyer": 3,
        "waiting for weeks": 2,
        "beschwerde": 3,
        "unzumutbar": 3,
        "enttäuscht": 2,
        "verärgert": 2,
        "unfreundlich": 2,
        "frechheit": 3,
        "anwalt": 3,
        "nie wieder": 3,
    },
    "general_inquiry": {
        "question": 1,
        "information": 1,
        "how do i": 1,
        "how can i": 1,
        "opening hours": 2,
        "where": 1,
        "app": 1,
        "manual": 1,
        "frage": 1,
        "auskunft": 1,
        "öffnungszeiten": 2,
        "wie kann ich": 1,
        "anleitung": 1,
    },
}

# Urgency rules: first match wins, checked from most to least urgent.
URGENCY_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "critical",
        (
            "accident",
            "crash",
            "smoke",
            "fire",
            "burning smell",
            "brakes failed",
            "brake failure",
            "brakes don't work",
            "injured",
            "children in the car",
            "kids in the car",
            "unfall",
            "rauch",
            "feuer",
            "brandgeruch",
            "bremsen versagen",
            "verletzt",
            "kinder im auto",
        ),
    ),
    (
        "high",
        (
            "breakdown",
            "broke down",
            "stranded",
            "won't start",
            "wont start",
            "does not start",
            "doesn't start",
            "warning light",
            "cannot drive",
            "can't drive",
            "urgent",
            "asap",
            "immediately",
            "lawyer",
            "panne",
            "liegengeblieben",
            "springt nicht an",
            "warnleuchte",
            "kann nicht fahren",
            "dringend",
            "sofort",
            "anwalt",
        ),
    ),
    (
        "low",
        (
            "no rush",
            "whenever",
            "just wondering",
            "feedback",
            "opening hours",
            "keine eile",
            "nur eine frage",
            "öffnungszeiten",
        ),
    ),
]

_DE_MARKERS = (
    " ich ",
    " und ",
    " nicht ",
    " mein ",
    " meine ",
    " bitte ",
    " das ",
    " ist ",
    " der ",
    " die ",
    " mit ",
    " ein ",
    " eine ",
    " auto ",
    " wagen ",
    " hallo ",
    " danke ",
)
_EN_MARKERS = (
    " i ",
    " and ",
    " not ",
    " my ",
    " please ",
    " the ",
    " is ",
    " with ",
    " a ",
    " car ",
    " hello ",
    " thanks ",
    " thank ",
    " you ",
)

# German words that are common in car-service messages; short messages
# ("Unfall! Rauch!") have no stopwords, so domain words carry the signal.
_DE_VOCAB = (
    "unfall",
    "rauch",
    "motorraum",
    "hilfe",
    "panne",
    "rechnung",
    "laden",
    "termin",
    "werkstatt",
    "bremse",
    "fahrzeug",
    "kaputt",
    "dringend",
    "sofort",
    "beschwerde",
    "frage",
    "danke",
)

VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
PLATE_RE = re.compile(r"\b[A-ZÄÖÜ]{1,3}[- ][A-Z]{1,2} ?\d{1,4}[EH]?\b")


@dataclass
class TriageResult:
    language: str
    category: str
    urgency: str
    confidence: float
    matched: list[str] = field(default_factory=list)
    entities: dict[str, str] = field(default_factory=dict)
    engine: str = "rules"

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)


def detect_language(text: str) -> str:
    t = f" {text.lower()} "
    t = re.sub(r"[^\wäöüß ]", " ", t)
    de = sum(t.count(m) for m in _DE_MARKERS) + 2 * len(re.findall(r"[äöüß]", t))
    de += sum(2 for w in _DE_VOCAB if w in t)
    en = sum(t.count(m) for m in _EN_MARKERS)
    return "de" if de > en else "en"


def _hits(text: str, keyword: str) -> bool:
    # match at a word start so "app" doesn't hit "appointment"-free words wrongly
    return re.search(r"(?<![\wäöüß])" + re.escape(keyword), text) is not None


def classify(text: str) -> TriageResult:
    low = text.lower()
    scores: dict[str, float] = {c: 0.0 for c in CATEGORIES}
    matched: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for cat, words in KEYWORDS.items():
        for kw, w in words.items():
            if _hits(low, kw):
                scores[cat] += w
                matched[cat].append(kw)

    total = sum(scores.values())
    if total == 0:
        category, confidence = "general_inquiry", 0.3
    else:
        # roadside beats repair on a tie: a stranded customer needs help now
        category = max(CATEGORIES, key=lambda c: (scores[c], -CATEGORIES.index(c)))
        confidence = round(scores[category] / total, 2)

    urgency = "normal"
    urgency_hits: list[str] = []
    for level, words in URGENCY_RULES:
        found = [w for w in words if _hits(low, w)]
        if found:
            urgency, urgency_hits = level, found
            break

    # a safety emergency with no other clue is handled by roadside assistance
    if urgency == "critical" and category == "general_inquiry":
        category, confidence = "roadside_assistance", max(confidence, 0.5)

    entities: dict[str, str] = {}
    if m := VIN_RE.search(text.upper()):
        entities["vin"] = m.group(0)
    if m := PLATE_RE.search(text):
        entities["licence_plate"] = m.group(0)

    return TriageResult(
        language=detect_language(text),
        category=category,
        urgency=urgency,
        confidence=confidence,
        matched=matched[category] + [f"urgency:{w}" for w in urgency_hits],
        entities=entities,
    )


# ---------------------------------------------------------------- replies

_REPLIES = {
    "en": {
        "greeting": "Hello {name},",
        "roadside_assistance": "we're sorry your vehicle has broken down. Please stay in a safe place. "
        "Our roadside assistance team has your request and will contact you shortly with an arrival time.",
        "workshop_repair": "thank you for your message. We'd be happy to arrange a workshop appointment. "
        "A service advisor will get back to you with available dates.",
        "charging_ev": "thank you for reaching out about charging. Our EV specialists will look into it. "
        "In the meantime, please check that the charging cable is fully plugged in at both ends.",
        "billing_invoice": "thank you for your message about your invoice. Our billing team will review it and get back to you.",
        "complaint": "we're sorry about your experience. We take your feedback seriously, and a team lead "
        "will personally review your case and contact you.",
        "general_inquiry": "thank you for your question. A member of our customer service team will reply shortly.",
        "critical": "If anyone is in danger, please call the emergency number 112 first.",
        "closing": "Your reference number is {ref}.\n\nKind regards,\nCustomer Service",
    },
    "de": {
        "greeting": "Hallo {name},",
        "roadside_assistance": "es tut uns leid, dass Ihr Fahrzeug liegengeblieben ist. Bitte bleiben Sie an "
        "einem sicheren Ort. Unser Pannendienst hat Ihre Anfrage erhalten und meldet sich in Kürze mit der Ankunftszeit.",
        "workshop_repair": "vielen Dank für Ihre Nachricht. Gerne vereinbaren wir einen Werkstatttermin. "
        "Ein Serviceberater meldet sich mit freien Terminen bei Ihnen.",
        "charging_ev": "vielen Dank für Ihre Anfrage zum Laden. Unsere E-Mobilitäts-Experten kümmern sich darum. "
        "Bitte prüfen Sie bis dahin, ob das Ladekabel an beiden Enden richtig eingesteckt ist.",
        "billing_invoice": "vielen Dank für Ihre Nachricht zu Ihrer Rechnung. Unser Abrechnungsteam prüft den "
        "Vorgang und meldet sich bei Ihnen.",
        "complaint": "es tut uns leid, dass Sie unzufrieden sind. Wir nehmen Ihr Feedback ernst; eine Teamleitung "
        "prüft Ihren Fall persönlich und kontaktiert Sie.",
        "general_inquiry": "vielen Dank für Ihre Frage. Ein Mitarbeiter unseres Kundenservice antwortet Ihnen in Kürze.",
        "critical": "Falls jemand in Gefahr ist, rufen Sie bitte zuerst den Notruf 112 an.",
        "closing": "Ihre Vorgangsnummer lautet {ref}.\n\nMit freundlichen Grüßen\nIhr Kundenservice",
    },
}


def draft_reply(result: TriageResult, customer_name: str | None, reference: str) -> str:
    t = _REPLIES.get(result.language, _REPLIES["en"])
    if customer_name:
        greeting = t["greeting"].format(name=customer_name)
    else:
        greeting = "Sehr geehrte Damen und Herren," if result.language == "de" else "Hello,"
    parts = [greeting, ""]
    if result.urgency == "critical":
        parts += [t["critical"], ""]
    body = t[result.category]
    if result.language == "en":  # English capitalises after the greeting, German does not
        body = body[0].upper() + body[1:]
    parts += [body, "", t["closing"].format(ref=reference)]
    return "\n".join(parts)
