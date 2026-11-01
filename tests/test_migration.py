"""An old database (created before customer_phone existed) is upgraded in place."""

import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_old_database_gets_phone_column():
    db = Path(tempfile.mkdtemp()) / "old.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE tickets (id INTEGER PRIMARY KEY, reference VARCHAR(20), created_at DATETIME, updated_at DATETIME,"
        " customer_name VARCHAR(120), customer_email VARCHAR(200), channel VARCHAR(20), message TEXT,"
        " language VARCHAR(5), category VARCHAR(40), urgency VARCHAR(10), confidence FLOAT, engine VARCHAR(20),"
        " matched TEXT, suggested_reply TEXT, status VARCHAR(20), servicenow_number VARCHAR(40),"
        " power_automate_notified BOOLEAN)"
    )
    con.execute(
        "INSERT INTO tickets VALUES (1,'SDC-000001','2026-11-01 10:00:00','2026-11-01 10:00:00','Old','old@example.com',"
        "'web','old ticket','en','general_inquiry','normal',0.3,'rules','','hi','new',NULL,0)"
    )
    con.commit()
    con.close()

    # fresh interpreter so app.db picks up this DATABASE_URL
    code = "from app.db import init_db; init_db()"
    env = {"DATABASE_URL": f"sqlite:///{db}", "PATH": ""}
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True)

    con = sqlite3.connect(db)
    cols = [r[1] for r in con.execute("PRAGMA table_info(tickets)")]
    assert "customer_phone" in cols
    assert con.execute("SELECT customer_name FROM tickets").fetchone()[0] == "Old"  # data kept
