"""Tailor resume content and generate DOCX + cover letter per job description."""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from docx import Document
from docx.shared import Pt
from services.profile import load_profile

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def extract_jd_keywords(jd: str, limit: int = 15) -> list[str]:
    profile = load_profile()
    jd_lower = jd.lower()
    hits = [s for s in profile["skills"] if s.lower() in jd_lower]
    extras = [
        "terraform", "kubernetes", "azure", "devsecops", "ci/cd", "sre",
        "prometheus", "grafana", "defender", "compliance", "automation",
        "python", "docker", "helm", "monitoring", "security",
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
    role = job_title if job_title else profile["title"].split("|")[0].strip()
    return f"{role}-focused engineer. {summary}"


def tailor_bullets(jd: str, max_bullets: int = 6) -> list[str]:
    profile = load_profile()
    bullets = profile["experience_highlights"].copy()

    def relevance(b: str) -> int:
        return sum(1 for k in extract_jd_keywords(jd, 20) if k.lower() in b.lower())

    bullets.sort(key=relevance, reverse=True)
    keywords = extract_jd_keywords(jd, 5)
    if keywords:
        opener = (
            f"Strong fit for this role with hands-on experience in "
            f"{', '.join(keywords[:4])} in production Azure environments."
        )
        if opener not in bullets:
            bullets.insert(0, opener)
    return bullets[:max_bullets]


def _jd_hook(jd: str, keywords: list[str]) -> str:
    """One sentence referencing what the JD asks for."""
    jd_lower = jd.lower()
    hooks = []
    if "devsecops" in jd_lower or "security" in jd_lower:
        hooks.append("integrating security across the SDLC with Azure Policy and Defender for Cloud")
    if "kubernetes" in jd_lower or "aks" in jd_lower:
        hooks.append("operating production AKS clusters with automated recovery and observability")
    if "terraform" in jd_lower or "iac" in jd_lower:
        hooks.append("Infrastructure as Code using Terraform and ARM templates")
    if "ci/cd" in jd_lower or "pipeline" in jd_lower:
        hooks.append("building CI/CD pipelines in Azure DevOps and GitHub Actions")
    if "sre" in jd_lower or "reliability" in jd_lower:
        hooks.append("SRE practices including monitoring, alerting, and MTTR reduction")
    if hooks:
        return hooks[0]
    return f"delivering solutions with {', '.join(keywords[:3])}"


def generate_cover_letter_snippet(job: dict) -> str:
    profile = load_profile()
    jd = job.get("description", "")
    keywords = extract_jd_keywords(jd, 8)
    title = job.get("title", "the open position")
    company = job.get("company", "your organization")
    hook = _jd_hook(jd, keywords)
    top_skills = ", ".join(keywords[:5]) if keywords else "Azure, AKS, DevSecOps, and CI/CD"

    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to apply for the {title} position at {company}. "
        f"With {profile['years_experience']} years of hands-on experience in cloud engineering and DevSecOps, "
        f"I have worked extensively with {top_skills} in production environments.\n\n"
        f"Your job description emphasizes requirements that align closely with my background — "
        f"particularly {hook}. "
        f"At Amdocs, I have reduced MTTR by 40% through AKS pod recovery automation, "
        f"achieved 90% reduction in manual compliance checks via Python tooling, "
        f"and improved monitoring coverage by 35% using Prometheus and Grafana on Azure.\n\n"
        f"I am AZ-104 certified and have built open-source tools for Azure security auditing, "
        f"cost governance, and compliance checking — demonstrating the automation-first mindset "
        f"this role requires. I would welcome the opportunity to bring this experience to {company}.\n\n"
        f"Thank you for your consideration. I look forward to discussing how I can contribute to your team.\n\n"
        f"Best regards,\n"
        f"{profile['name']}\n"
        f"{profile['phone']} | {profile['email']}\n"
        f"{profile['linkedin']}"
    )


def generate_tailored_docx(job: dict, output_path: Path | None = None) -> str:
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

    doc.add_paragraph(
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

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path.name

    safe_name = re.sub(r"[^\w\-]", "_", f"{company}_{title}")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"resume_{safe_name}_{ts}.docx"
    path = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(exist_ok=True)
    doc.save(str(path))
    return filename


def generate_application_package(job: dict, app_dir: Path) -> dict:
    """Generate tailored resume DOCX + cover letter for one job opening."""
    app_dir.mkdir(parents=True, exist_ok=True)
    jd = job.get("description", "")
    title = job.get("title", "")

    resume_path = app_dir / "resume.docx"
    cover_path = app_dir / "cover_letter.txt"
    meta_path = app_dir / "meta.json"

    generate_tailored_docx(job, output_path=resume_path)
    cover = generate_cover_letter_snippet(job)
    cover_path.write_text(cover, encoding="utf-8")

    summary = tailor_summary(jd, title)
    job_id = job["id"]
    meta = {
        "job_id": job_id,
        "title": title,
        "company": job.get("company", ""),
        "url": job.get("url", ""),
        "match_score": job.get("match_score", 0),
        "posted_at": job.get("posted_at", ""),
        "tailored_summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    base = f"applications/{job_id}"
    return {
        "resume_url": f"{base}/resume.docx",
        "cover_letter_url": f"{base}/cover_letter.txt",
        "cover_letter": cover,
        "tailored_summary": summary,
        "application_ready": True,
    }
