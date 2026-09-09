import re
from collections import Counter

DEFAULT_TARGET_TITLES = [
    "it support specialist",
    "it support engineer",
    "systems administrator",
    "system administrator",
    "help desk",
    "desktop support",
    "it administrator",
    "active directory administrator",
    "cybersecurity analyst",
    "junior security analyst",
    "jr soc analyst",
    "soc analyst",
    "technical support engineer",
]

DEFAULT_SKILLS = [
    "active directory", "group policy", "gpo", "cybersecurity", "soc",
    "splunk", "sentinelone", "edr", "network security", "incident response",
    "threat monitoring", "windows", "linux", "macos", "technical support",
    "zero trust", "ubiquiti", "firewall", "firewalls", "switches", "servers",
    "microsoft 365", "office 365", "azure", "entra", "intune", "vpn",
    "tcp/ip", "dns", "dhcp", "powershell"
]

SENIOR_TERMS = [
    "senior", "sr.", "lead", "principal", "manager", "director",
    "10+ years", "8+ years", "7+ years"
]

def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9+#./ -]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_skills(text: str, skills=None):
    skills = skills or DEFAULT_SKILLS
    n = normalize(text)
    return sorted({s for s in skills if normalize(s) in n})

def title_score(title: str, target_titles=None) -> float:
    target_titles = target_titles or DEFAULT_TARGET_TITLES
    t = normalize(title)
    if not t:
        return 0.0
    if any(x == t for x in target_titles):
        return 1.0
    if any(x in t or t in x for x in target_titles):
        return 0.9
    tokens = set(t.split())
    best = 0.0
    for target in target_titles:
        tt = set(target.split())
        if not tt:
            continue
        overlap = len(tokens & tt) / len(tokens | tt)
        best = max(best, overlap)
    return best

def seniority_penalty(title: str, description: str) -> int:
    hay = normalize(f"{title} {description}")
    penalty = 0
    for term in SENIOR_TERMS:
        if normalize(term) in hay:
            penalty = max(penalty, 25)
    # Years requirement heuristic
    years = re.findall(r"(\d+)\+?\s+years", hay)
    if years:
        max_years = max(map(int, years))
        if max_years >= 8:
            penalty = max(penalty, 30)
        elif max_years >= 5:
            penalty = max(penalty, 15)
    return penalty

def required_qualification_penalty(description: str, resume_text: str) -> int:
    d = normalize(description)
    r = normalize(resume_text)
    penalty = 0

    patterns = [
        ("cissp", 12),
        ("security+", 8),
        ("ccna", 8),
        ("bachelor", 6),
        ("master", 10),
    ]
    for phrase, p in patterns:
        if ("required" in d or "must have" in d) and phrase in d and phrase not in r:
            penalty += p
    return min(penalty, 25)

def score_job(resume_text: str, title: str, description: str, location: str = "", preferred_locations=None):
    preferred_locations = preferred_locations or []
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(extract_skills(description + " " + title))

    if job_skills:
        skill_overlap = len(resume_skills & job_skills) / len(job_skills)
    else:
        skill_overlap = 0.25

    t_score = title_score(title)

    location_score = 0.5
    if preferred_locations:
        loc = normalize(location)
        location_score = 1.0 if any(normalize(p) in loc for p in preferred_locations) else 0.3

    raw = (
        55 * skill_overlap +
        30 * t_score +
        15 * location_score
    )

    penalty = seniority_penalty(title, description)
    penalty += required_qualification_penalty(description, resume_text)

    score = max(0, min(100, round(raw - penalty)))

    if score >= 80:
        bucket = "Apply Queue"
    elif score >= 65:
        bucket = "Review"
    else:
        bucket = "Skip"

    matched = sorted(resume_skills & job_skills)
    missing = sorted(job_skills - resume_skills)

    return {
        "score": score,
        "bucket": bucket,
        "matched_skills": matched,
        "missing_skills": missing,
        "penalty": penalty,
    }
