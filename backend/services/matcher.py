"""Match jobs to resume profile with keyword scoring."""

import re
from services.profile import load_profile


def tokenize(text: str) -> set[str]:
    text = text.lower()
    tokens = set(re.findall(r"[a-z0-9+#/.-]{2,}", text))
    # also capture multi-word skills
    for skill in load_profile()["skills"]:
        if skill.lower() in text.lower():
            tokens.add(skill.lower())
    return tokens


def score_job(job: dict) -> dict:
    profile = load_profile()
    jd = f"{job.get('title','')} {job.get('description','')} {job.get('company','')}".lower()

    # Exclude senior-only or irrelevant
    for bad in profile.get("exclude_keywords", []):
        if bad.lower() in jd:
            job["match_score"] = 0
            job["match_reason"] = f"Excluded: contains '{bad}'"
            job["matched_skills"] = []
            return job

    profile_tokens = tokenize(" ".join(profile["skills"] + profile["target_roles"]))
    jd_tokens = tokenize(jd)

    role_hits = sum(1 for r in profile["target_roles"] if r.lower() in jd)
    skill_hits = [s for s in profile["skills"] if s.lower() in jd]
    overlap = len(profile_tokens & jd_tokens)

    score = min(100, role_hits * 15 + len(skill_hits) * 4 + overlap * 2)
    if profile["years_experience"] <= 3 and any(x in jd for x in ["8+ years", "7+ years", "senior architect"]):
        score = max(0, score - 30)

    job["match_score"] = score
    job["matched_skills"] = skill_hits[:12]
    job["match_reason"] = f"{len(skill_hits)} skills matched, role fit {role_hits}/6"
    return job


def filter_and_rank(jobs: list[dict], min_score: int = 40) -> list[dict]:
    scored = [score_job(j) for j in jobs]
    filtered = [j for j in scored if j.get("match_score", 0) >= min_score]
    return sorted(filtered, key=lambda x: x.get("match_score", 0), reverse=True)
