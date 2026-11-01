import pytest

from app.triage import classify, detect_language, draft_reply

CASES = [
    # message, language, category, urgency
    ("My car broke down on the motorway and won't start, I'm stranded.", "en", "roadside_assistance", "high"),
    ("Mein Auto ist auf der Autobahn liegengeblieben, Pannenhilfe bitte!", "de", "roadside_assistance", "high"),
    ("I'd like to book a workshop appointment for my yearly inspection, no rush.", "en", "workshop_repair", "low"),
    ("Ich brauche einen Termin in der Werkstatt, die Bremse macht ein Geräusch.", "de", "workshop_repair", "normal"),
    ("My wallbox stopped charging and the charging cable light is red.", "en", "charging_ev", "normal"),
    ("Die Ladestation lädt nicht, Ladekabel blinkt.", "de", "charging_ev", "normal"),
    ("I was charged twice, please refund the second payment on my invoice.", "en", "billing_invoice", "normal"),
    ("Die Rechnung ist falsch, ich wurde doppelt abgebucht. Bitte um Erstattung.", "de", "billing_invoice", "normal"),
    ("This is unacceptable, the staff was rude and I'm very disappointed. Complaint!", "en", "complaint", "normal"),
    ("Accident on the highway, there is smoke coming from the engine!", "en", "roadside_assistance", "critical"),
    ("Unfall! Rauch aus dem Motorraum.", "de", "roadside_assistance", "critical"),
    ("What are your opening hours on Saturday?", "en", "general_inquiry", "low"),
]


@pytest.mark.parametrize("msg,lang,cat,urg", CASES)
def test_classify(msg, lang, cat, urg):
    r = classify(msg)
    assert r.language == lang
    assert r.category == cat
    assert r.urgency == urg
    assert 0 <= r.confidence <= 1


def test_accident_is_confident_roadside():
    for msg in ("Accident on the A100, smoke from the engine!", "Unfall auf der A100, Rauch!"):
        r = classify(msg)
        assert r.category == "roadside_assistance" and r.urgency == "critical"
        assert r.confidence == 1.0 and "urgency:" in " ".join(r.matched)


def test_explainable_matches():
    r = classify("Wallbox is not charging")
    assert "wallbox" in r.matched


def test_unknown_message_falls_back():
    r = classify("Hello there")
    assert r.category == "general_inquiry"
    assert r.confidence < 0.5


def test_entities():
    r = classify("Car with VIN WDD2220821A123456 and plate B-MB 1234 needs service")
    assert r.entities["vin"] == "WDD2220821A123456"
    assert r.entities["licence_plate"].startswith("B-MB")


def test_language_detection_umlauts():
    assert detect_language("Grüße, das Fahrzeug ist kaputt") == "de"
    assert detect_language("Thanks, the car is fine") == "en"


def test_reply_critical_mentions_112_and_reference():
    r = classify("Unfall, Rauch!")
    reply = draft_reply(r, "Anna", "SDC-000001")
    assert "112" in reply and "SDC-000001" in reply and reply.startswith("Hallo Anna,")


def test_reply_english_capitalised_without_name():
    r = classify("Please refund my invoice")
    reply = draft_reply(r, None, "SDC-000002")
    assert reply.startswith("Hello,\n\nThank you")
