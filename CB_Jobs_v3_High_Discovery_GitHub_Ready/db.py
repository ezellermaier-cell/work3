import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd

APP_DIR = Path.home() / "RemoteTechJobMatcher"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "job_tracker.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    location TEXT,
    description TEXT,
    source TEXT,
    remote_verified INTEGER DEFAULT 1,
    date_found TEXT,
    date_applied TEXT,
    match_score INTEGER,
    bucket TEXT,
    status TEXT,
    resume_version TEXT,
    cover_letter TEXT,
    notes TEXT,
    unique_key TEXT UNIQUE
);
"""

def conn():
    c = sqlite3.connect(DB_PATH)
    c.execute(SCHEMA)
    cols = {row[1] for row in c.execute("PRAGMA table_info(jobs)").fetchall()}
    if "source" not in cols:
        c.execute("ALTER TABLE jobs ADD COLUMN source TEXT")
    if "remote_verified" not in cols:
        c.execute("ALTER TABLE jobs ADD COLUMN remote_verified INTEGER DEFAULT 1")
    c.commit()
    return c

def make_key(company, title, url):
    return f"{(company or '').strip().lower()}|{(title or '').strip().lower()}|{(url or '').strip().lower()}"

def add_job(company, title, url="", location="", description="", match_score=0,
            bucket="Review", source="", remote_verified=True):
    c = conn()
    key = make_key(company, title, url)
    try:
        c.execute("""
            INSERT INTO jobs (
                company,title,url,location,description,source,remote_verified,
                date_found,match_score,bucket,status,unique_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company, title, url, location, description, source,
            1 if remote_verified else 0,
            datetime.now().strftime("%Y-%m-%d"),
            int(match_score), bucket, "Not Applied", key
        ))
        c.commit()
        return True, "Added"
    except sqlite3.IntegrityError:
        return False, "Duplicate"

def get_jobs():
    c = conn()
    return pd.read_sql_query("SELECT * FROM jobs ORDER BY id DESC", c)

def update_job(job_id, status=None, notes=None, resume_version=None, cover_letter=None):
    c = conn()
    fields, vals = [], []
    if status is not None:
        fields += ["status=?"]
        vals += [status]
        if status == "Applied":
            fields += ["date_applied=?"]
            vals += [datetime.now().strftime("%Y-%m-%d")]
    if notes is not None:
        fields += ["notes=?"]
        vals += [notes]
    if resume_version is not None:
        fields += ["resume_version=?"]
        vals += [resume_version]
    if cover_letter is not None:
        fields += ["cover_letter=?"]
        vals += [cover_letter]
    if not fields:
        return
    vals.append(job_id)
    c.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", vals)
    c.commit()

def delete_job(job_id):
    c = conn()
    c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    c.commit()
