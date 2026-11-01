"""Fill a running ServiceDesk Copilot with 30 realistic demo requests.

    python scripts/seed_demo.py                       # local (http://localhost:8000)
    python scripts/seed_demo.py https://<your-app>    # Azure / any other URL

Mix of English and German, all categories and urgencies, with name, e-mail
and phone, and random statuses. All people and numbers are made up.
"""

import random
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")

# name, phone, channel, message
REQUESTS = [
    # --- roadside assistance
    ("Max Weber", "+49 151 2034411", "phone", "My car broke down on the A100 and won't start. I'm stranded, please help asap."),
    ("Lea Fischer", "+49 160 9988123", "phone", "Unfall auf der Autobahn A2, Rauch aus dem Motorraum!"),
    ("Tom Becker", "+49 176 4455667", "chat", "Flat tyre on the motorway near Potsdam, I need a tow."),
    ("Jana Krüger", "+49 152 3311224", "phone", "Mein Wagen ist liegengeblieben und springt nicht an. Bitte Pannenhilfe!"),
    (
        "Omar Haddad",
        "+49 157 7788990",
        "phone",
        "Accident at a junction in Spandau, the car is smoking. Kids in the car are fine.",
    ),
    # --- workshop / repair
    ("Jonas Müller", "+49 30 5566778", "web", "Ich brauche einen Termin in der Werkstatt, die Bremse macht ein Geräusch."),
    ("Emma Davis", None, "web", "I'd like to book an inspection appointment next month, whenever works."),
    ("Paul Hoffmann", "+49 171 2233445", "phone", "Warnleuchte ist an, kann ich noch fahren? Dringend!"),
    (
        "Chloe Martin",
        "+49 162 1239876",
        "email",
        "There's a strange noise from the front left wheel. Can I get a repair appointment?",
    ),
    ("Felix Wagner", None, "web", "Wann ist meine nächste Inspektion fällig? Ich hätte gern einen Termin im Januar."),
    ("Aisha Khan", "+49 159 6677889", "email", "I received a recall letter for my car. How do I book the workshop visit?"),
    # --- charging / EV
    ("Anna Schmidt", "+49 30 1234567", "email", "Hallo, meine Wallbox lädt seit gestern nicht mehr, das Ladekabel blinkt rot."),
    ("Ella Becker", None, "web", "The range on my electric car dropped a lot since the update. Charging is slow too."),
    ("Lukas Braun", "+49 174 5544332", "chat", "Die Ladestation am Hotel lädt nicht, was kann ich tun?"),
    ("Priya Nair", "+49 155 8899001", "email", "My charging cable is stuck in the charger and won't unlock."),
    ("Mia Wagner", None, "chat", "Wie viele kWh lädt die Wallbox pro Stunde? Die Reichweite reicht nicht."),
    # --- billing / invoice
    ("Liam Brown", "+49 176 1112223", "email", "I was charged twice for my last inspection. Please refund the second payment."),
    ("Sara Weiß", None, "email", "Die Rechnung ist falsch, ich wurde doppelt abgebucht. Bitte um Erstattung."),
    ("Noah Wilson", "+49 152 9090909", "web", "Can you send me a receipt for the oil change? I need it for my company."),
    ("Hannah Koch", None, "email", "Ich habe noch keine Gutschrift für die stornierte Reparatur erhalten."),
    ("Diego Alvarez", "+49 163 2121212", "phone", "The invoice price is higher than the quote I was given. I was overcharged."),
    # --- complaints
    (
        "Sofia Rossi",
        "+49 151 7070707",
        "email",
        "This is unacceptable. I've been waiting for weeks and the staff was rude. Complaint!",
    ),
    ("Ben Schulz", None, "email", "Das ist eine Frechheit. Ich warte seit drei Wochen auf mein Auto. Beschwerde!"),
    (
        "Grace Lee",
        "+49 157 3434343",
        "web",
        "I'm very disappointed with the service. If this isn't fixed I'll talk to my lawyer.",
    ),
    ("Mehmet Yilmaz", None, "phone", "Der Mitarbeiter am Telefon war sehr unfreundlich, ich bin enttäuscht."),
    # --- general inquiries
    ("Ben Taylor", None, "chat", "What are your opening hours on Saturday? No rush."),
    ("Laura Richter", None, "chat", "Wie sind Ihre Öffnungszeiten am Samstag? Nur eine Frage."),
    ("Kenji Sato", "+49 160 5656565", "web", "How do I connect my phone to the app? Is there a manual?"),
    ("Nina Vogel", None, "email", "Wie kann ich mein Handy mit der App verbinden?"),
    ("Arjun Mehta", None, "web", "Hello, is there a dealership near Alexanderplatz? Just wondering."),
]

STATUSES = ["new", "new", "in_progress", "waiting_for_customer", "resolved"]


def email_for(name: str) -> str:
    plain = name.lower().replace(" ", ".")
    for a, b in (("ü", "ue"), ("ö", "oe"), ("ä", "ae"), ("ß", "ss")):
        plain = plain.replace(a, b)
    return f"{plain}@example.com"


def main() -> None:
    random.seed(7)
    created = 0
    with httpx.Client(base_url=BASE, timeout=20) as c:
        for name, phone, channel, msg in REQUESTS:
            body = {"message": msg, "customer_name": name, "customer_email": email_for(name), "channel": channel}
            if phone:
                body["customer_phone"] = phone
            t = c.post("/api/tickets", json=body).raise_for_status().json()
            status = random.choice(STATUSES)
            if status != "new":
                c.patch(f"/api/tickets/{t['reference']}", json={"status": status}).raise_for_status()
            created += 1
            print(f"{t['reference']}  {t['urgency']:8}  {t['category']:20}  {t['language']}  {status:21} {name}")
    print(f"\n{created} tickets created on {BASE}")


if __name__ == "__main__":
    main()
