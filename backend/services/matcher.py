"""Match jobs to resume — boost DevOps / Kubernetes / Cloud / IAM relevance."""

import re
from services.profile import load_profile

DOMAIN_BOOST_TERMS = [
    "devops", "devsecops", "kubernetes", "k8s", "cloud", "azure", "aws",
    "iam", "identity", "rbac", "entra id", "terraform", "aks", "sre",
    "platform engineer", "helm", "docker", "ci/cd", "cloud security",
]


def tokenize(text: str) -> set[str]:
    text = text.lower()
    tokens = set(re.findall(r"[a-z0-9+#/.-]{2,}", text))
    for skill in load_profile()["skills"]:
        if skill.lower() in text:
            tokens.add(skill.lower())
    return tokens


def score_job(job: dict) -> dict:
    profile = load_profile()
    title = (job.get("title") or "").lower()
    jd = f"{title} {job.get('description', '')} {job.get('company', '')}".lower()

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

    # Strong title match for target domains
    domain_title_hits = sum(1 for t in DOMAIN_BOOST_TERMS if t in title)
    domain_body_hits = sum(1 for t in DOMAIN_BOOST_TERMS if t in jd)

    score = min(
        100,
        role_hits * 12
        + len(skill_hits) * 4
        + overlap * 1
        + domain_title_hits * 10
        + min(domain_body_hits, 8) * 2,
    )

    if profile["years_experience"] <= 3 and any(
        x in jd for x in ["8+ years", "7+ years", "10+ years", "principal architect"]
    ):
        score = max(0, score - 25)

    # Soft-penalize pure software/frontend titles with no infra keywords
    if any(x in title for x in ["frontend", "react native", "android developer", "ios developer"]):
        if domain_title_hits == 0:
            score = max(0, score - 40)

    job["match_score"] = score
    job["matched_skills"] = skill_hits[:12]
    job["match_reason"] = (
        f"{len(skill_hits)} skills, {role_hits} roles, "
        f"{domain_title_hits} domain terms in title"
    )
    return job


def filter_and_rank(jobs: list[dict], min_score: int = 30) -> list[dict]:
    scored = [score_job(j) for j in jobs]
    filtered = [j for j in scored if j.get("match_score", 0) >= min_score]
    return sorted(filtered, key=lambda x: x.get("match_score", 0), reverse=True)
