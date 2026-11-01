"""Send realistic demo requests to a running ServiceDesk Copilot.

    python scripts/seed_demo.py                       # local
    python scripts/seed_demo.py https://<your-app>    # Azure

Good for screenshots and for giving the Power BI report something to show.
"""

import random
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")

MESSAGES = [
    ("Max Weber", "My car broke down on the A100 and won't start. I'm stranded, please help asap.", "phone"),
    ("Anna Schmidt", "Hallo, meine Wallbox lädt seit gestern nicht mehr, das Ladekabel blinkt rot.", "email"),
    ("Liam Brown", "I was charged twice for my last inspection. Please refund the second payment.", "web"),
    ("Jonas Müller", "Ich brauche einen Termin in der Werkstatt, die Bremse macht ein Geräusch.", "web"),
    ("Sofia Rossi", "This is unacceptable. I've been waiting for weeks and the staff was rude. Complaint!", "email"),
    ("Lea Fischer", "Unfall auf der Autobahn, Rauch aus dem Motorraum!", "phone"),
    ("Noah Wilson", "What are your opening hours on Saturday? No rush.", "chat"),
    ("Mia Wagner", "Die Rechnung ist falsch, ich wurde doppelt abgebucht. Bitte um Erstattung.", "email"),
    ("Ella Becker", "The range on my electric car dropped a lot since the update. Charging is slow too.", "web"),
    ("Paul Hoffmann", "Warnleuchte ist an, kann ich noch fahren? Dringend!", "phone"),
    ("Emma Davis", "I'd like to book an inspection appointment next month, whenever works.", "web"),
    ("Ben Schulz", "How do I connect my phone to the app? Is there a manual?", "chat"),
]


def main() -> None:
    statuses = ["new", "in_progress", "waiting_for_customer", "resolved"]
    with httpx.Client(base_url=BASE, timeout=20) as c:
        for name, msg, channel in MESSAGES:
            email = name.lower().replace(" ", ".").replace("ü", "ue") + "@example.com"
            t = (
                c.post("/api/tickets", json={"message": msg, "customer_name": name, "customer_email": email, "channel": channel})
                .raise_for_status()
                .json()
            )
            status = random.choice(statuses)
            if status != "new":
                c.patch(f"/api/tickets/{t['reference']}", json={"status": status}).raise_for_status()
            print(f"{t['reference']}  {t['urgency']:8}  {t['category']:20}  {t['language']}  -> {status}")


if __name__ == "__main__":
    main()
