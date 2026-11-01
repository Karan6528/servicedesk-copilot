"""Create docs/power-platform/sample_tickets.csv: ~400 synthetic tickets over 90 days.

Uses the real triage engine, so categories/urgency match what the app would produce.
    python -m scripts.make_powerbi_sample
"""

import csv
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.triage import classify, draft_reply

random.seed(42)
OUT = Path(__file__).resolve().parents[1] / "docs" / "power-platform" / "sample_tickets.csv"

TEMPLATES = {
    "en": [
        "My car broke down on the {road} and won't start. I'm stranded.",
        "The warning light is on, can I still drive? Urgent please.",
        "I'd like to book an inspection appointment next {when}.",
        "There is a strange noise from the brake when I stop.",
        "My wallbox stopped charging, the charging cable light is red.",
        "The range dropped a lot since the update. Charging is slow.",
        "I was charged twice for my last service. Please refund the payment.",
        "My invoice shows the wrong price for the oil change.",
        "This is unacceptable, I've been waiting for weeks. Complaint!",
        "The staff at the branch was rude, I'm very disappointed.",
        "What are your opening hours on Saturday? No rush.",
        "How do I connect my phone to the app?",
        "Accident on the {road}, there is smoke from the engine!",
    ],
    "de": [
        "Mein Auto ist auf der {road} liegengeblieben und springt nicht an.",
        "Die Warnleuchte ist an, kann ich noch fahren? Dringend!",
        "Ich möchte einen Termin für die Inspektion im {when_de}.",
        "Die Bremse macht ein Geräusch, bitte Werkstatttermin.",
        "Meine Wallbox lädt nicht mehr, das Ladekabel blinkt rot.",
        "Die Reichweite ist seit dem Update gesunken, laden dauert lange.",
        "Ich wurde doppelt abgebucht, bitte um Erstattung.",
        "Die Rechnung für die Wartung ist falsch.",
        "Das ist eine Frechheit, ich warte seit Wochen. Beschwerde!",
        "Der Mitarbeiter war unfreundlich, ich bin enttäuscht.",
        "Wie sind Ihre Öffnungszeiten am Samstag? Nur eine Frage.",
        "Wie kann ich mein Handy mit der App verbinden?",
        "Unfall auf der {road}, Rauch aus dem Motorraum!",
    ],
}
ROADS = ["A100", "A2", "A9", "A10", "B96", "A7"]
FIRST = ["Max", "Anna", "Liam", "Lea", "Jonas", "Sofia", "Noah", "Mia", "Paul", "Emma", "Ben", "Ella", "Lukas", "Hanna"]
LAST = ["Weber", "Schmidt", "Brown", "Fischer", "Müller", "Rossi", "Wilson", "Wagner", "Becker", "Schulz", "Koch"]
CHANNELS = ["web", "email", "phone", "chat"]
CH_WEIGHTS = [4, 3, 2, 1]


def main() -> None:
    now = datetime(2026, 10, 31, 18, 0, tzinfo=UTC)
    rows = []
    for i in range(1, 401):
        lang = random.choices(["de", "en"], weights=[60, 40])[0]
        tpl = random.choice(TEMPLATES[lang])
        msg = tpl.format(
            road=random.choice(ROADS), when=random.choice(["week", "month"]), when_de=random.choice(["Dezember", "Januar"])
        )
        r = classify(msg)
        created = now - timedelta(days=random.uniform(0, 90), hours=random.uniform(0, 10))
        age_days = (now - created).days
        status = "resolved" if age_days > 14 else random.choice(["new", "in_progress", "waiting_for_customer", "resolved"])
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        ref = f"SDC-{i:06d}"
        escalated = r.urgency in ("critical", "high")
        rows.append(
            {
                "reference": ref,
                "created_at": created.isoformat(timespec="seconds"),
                "customer_name": name,
                "customer_email": name.lower().replace(" ", ".").replace("ü", "ue") + "@example.com",
                "channel": random.choices(CHANNELS, CH_WEIGHTS)[0],
                "message": msg,
                "language": r.language,
                "category": r.category,
                "urgency": r.urgency,
                "confidence": r.confidence,
                "suggested_reply": draft_reply(r, name, ref).replace("\n", " "),
                "status": status,
                "servicenow_number": f"INC{10000 + i:07d}" if escalated else "",
            }
        )
    rows.sort(key=lambda x: x["created_at"])
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
