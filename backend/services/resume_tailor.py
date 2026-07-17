"""Tailor resume content and generate DOCX per job description."""

import re
from pathlib import Path
from datetime import datetime
from docx import Document
from docx.shared import Pt
from services.profile import load_profile

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def extract_jd_keywords(jd: str, limit: int = 15) -> list[str]:
    profile = load_profile()
    jd_lower = jd.lower()
    hits = [s for s in profile["skills"] if s.lower() in jd_lower]
    # Common cloud keywords in JD
    extras = [
        "terraform", "kubernetes", "azure", "devsecops", "ci/cd", "sre",
        "prometheus", "grafana", "defender", "compliance", "automation",
        "python", "docker", "helm", "monitoring", "security"
    ]
    for e in extras:
        if e in jd_lower and e.title() not in hits and e.upper() not in hits:
            hits.append(e.title() if e != "ci/cd" else "CI/CD")
    return hits[:limit]


def tailor_summary(jd: str, job_title: str) -> str:
    profile = load_profile()
    keywords = extract_jd_keywords(jd, 8)
    top = ", ".join(keywords[:6]) if keywords else "Azure, AKS, CI/CD, DevSecOps"
    summary = profile["summary_template"].format(years=profile["years_experience"], top_skills=top)
    # Lead with job-relevant title
    role = job_title if job_title else profile["title"].split("|")[0].strip()
    return f"{role}-focused engineer. {summary}"


def tailor_bullets(jd: str, max_bullets: int = 6) -> list[str]:
    profile = load_profile()
    jd_lower = jd.lower()
    bullets = profile["experience_highlights"].copy()

    # Prioritize bullets matching JD keywords
    def relevance(b: str) -> int:
        return sum(1 for k in extract_jd_keywords(jd, 20) if k.lower() in b.lower())

    bullets.sort(key=relevance, reverse=True)

    # Inject JD-specific opener if strong match
    keywords = extract_jd_keywords(jd, 5)
    if keywords:
        opener = (
            f"Strong fit for this role with hands-on experience in "
            f"{', '.join(keywords[:4])} in production Azure environments."
        )
        if opener not in bullets:
            bullets.insert(0, opener)

    return bullets[:max_bullets]


def generate_tailored_docx(job: dict) -> str:
    profile = load_profile()
    jd = job.get("description", "")
    title = job.get("title", "Cloud Engineer")
    company = job.get("company", "")

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    name = doc.add_paragraph()
    nr = name.add_run(profile["name"])
    nr.bold = True
    nr.font.size = Pt(16)

    headline = doc.add_paragraph()
    hr = headline.add_run(f"Tailored for: {title} at {company}")
    hr.bold = True
    hr.font.size = Pt(11)

    contact = doc.add_paragraph(
        f"{profile['location']} | {profile['phone']} | {profile['email']}\n"
        f"LinkedIn: {profile['linkedin']} | GitHub: {profile['github']}"
    )

    doc.add_paragraph("PROFESSIONAL SUMMARY").runs[0].bold = True
    doc.add_paragraph(tailor_summary(jd, title))

    doc.add_paragraph("RELEVANT EXPERIENCE HIGHLIGHTS").runs[0].bold = True
    for b in tailor_bullets(jd):
        doc.add_paragraph(b, style="List Bullet")

    doc.add_paragraph("KEY SKILLS FOR THIS ROLE").runs[0].bold = True
    doc.add_paragraph(", ".join(extract_jd_keywords(jd, 20)))

    doc.add_paragraph("CERTIFICATIONS").runs[0].bold = True
    for c in profile["certifications"]:
        doc.add_paragraph(c, style="List Bullet")

    safe_name = re.sub(r"[^\w\-]", "_", f"{company}_{title}")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"resume_{safe_name}_{ts}.docx"
    path = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(exist_ok=True)
    doc.save(str(path))
    return filename


def generate_cover_letter_snippet(job: dict) -> str:
    profile = load_profile()
    keywords = extract_jd_keywords(job.get("description", ""), 5)
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am applying for the {job.get('title')} role at {job.get('company')}. "
        f"With {profile['years_experience']} years of production experience on Azure, AKS, and DevSecOps, "
        f"I have direct experience with {', '.join(keywords[:4])}. "
        f"I have built automation that reduced MTTR by 40% and cut manual ops work by up to 90%. "
        f"I would welcome the opportunity to contribute to your team.\n\n"
        f"Best regards,\n{profile['name']}"
    )
