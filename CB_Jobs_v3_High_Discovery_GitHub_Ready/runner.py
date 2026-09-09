from datetime import datetime
from zoneinfo import ZoneInfo

from matcher import score_job
from db import add_job
from sources import fetch_selected_sources

EASTERN = ZoneInfo("America/New_York")

DEFAULT_SOURCES = ["Remotive", "Remote OK", "Jobicy", "Himalayas", "Arbeitnow", "We Work Remotely"]

def run_job_search(resume_text, apply_threshold=72, review_threshold=50, sources=None):
    if not resume_text.strip():
        raise ValueError("No resume is loaded.")

    sources = sources or DEFAULT_SOURCES
    jobs, errors = fetch_selected_sources(sources)

    added = 0
    duplicates = 0
    reviewed = 0

    preferred_locations = [
        "USA", "United States", "US", "Worldwide", "Anywhere", "Remote"
    ]

    for job in jobs:
        result = score_job(
            resume_text,
            job["title"],
            job["description"],
            job["location"],
            preferred_locations,
        )

        score = result["score"]
        if score >= apply_threshold:
            bucket = "Apply Queue"
        elif score >= review_threshold:
            bucket = "Review"
        else:
            bucket = "Skip"

        ok, _ = add_job(
            job["company"],
            job["title"],
            job["url"],
            job["location"],
            job["description"],
            score,
            bucket,
            source=job["source"],
            remote_verified=True,
        )

        if ok:
            added += 1
            if bucket != "Skip":
                reviewed += 1
        else:
            duplicates += 1

    return {
        "timestamp": datetime.now(EASTERN).strftime("%Y-%m-%d %I:%M %p %Z"),
        "fetched": len(jobs),
        "added": added,
        "duplicates": duplicates,
        "review_candidates": reviewed,
        "errors": errors,
    }
