"""Tailor resume content and generate DOCX + cover letter per job description.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from docx import Document
from docx.shared import Pt
from services.profile import load_profile

OUTPUT_DIR = Path(__file__).parent.parent / "output"
BASE_RESUME_PATH = Path(os.getenv("BASE_RESUME_DOCX", "shared/base_resume.docx"))


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


def _doc_text(doc: Document) -> str:
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def compute_ats_score(text: str, jd_keywords: list[str]) -> float:
    """Simple ATS-like scorer (0..10). Measures presence of JD keywords in resume text.

    This is intentionally conservative and transparent: it looks for exact keyword text
    (case-insensitive) and returns matched / total * 10.
    """
    if not jd_keywords:
        return 10.0
    t = text.lower()
    total = len(jd_keywords)
    matched = 0
    for k in jd_keywords:
        if not k:
            continue
        if k.lower() in t:
            matched += 1
    return round((matched / total) * 10.0, 2)


def humanize_text(s: str) -> str:
    """Apply light, deterministic rewrites so text reads like a human-written resume/cover letter.

    Rules are conservative (no invented facts):
    - Replace corporate-ese with concise phrases
    - Use contractions where appropriate
    - Shorten very long sentences
    - Remove or replace filler phrases
    """
    if not s:
        return s

    # Common phrase replacements (case-insensitive)
    replacements = [
        (r"I am writing to apply for", "I'm excited to apply for"),
        (r"I am writing to apply", "I'm excited to apply"),
        (r"I would welcome the opportunity to bring this experience to", "I'd welcome a chance to discuss how I can help"),
        (r"demonstrating the automation-first mindset( this role requires)?", "showing measurable automation and security improvements"),
        (r"Your job description emphasizes requirements that align closely with my background\s*[-—]*\s*particularly", "Your job emphasizes requirements that match my background, especially"),
        (r"Thank you for your consideration\. I look forward to discussing how I can contribute to your team\.", "Thanks for your time — I look forward to speaking."),
        (r"Thank you for your consideration\. I look forward to discussing", "Thanks for your time — I look forward to speaking about"),
        (r"I am AZ-104 certified", "I'm AZ-104 certified"),
        (r"I am", "I'm"),
    ]

    out = s
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.I)

    # Remove duplicate whitespace
    out = re.sub(r"[ \t]+", " ", out)

    # Shorten very long sentences by splitting on the first comma if > 140 chars
    sentences = re.split(r'(?<=[.!?])\s+', out)
    for i, sent in enumerate(sentences):
        if len(sent) > 140 and "," in sent:
            parts = sent.split(",", 1)
            sentences[i] = parts[0].strip() + ". " + parts[1].strip()

    out = " ".join(s.strip() for s in sentences if s and s.strip())

    # Final tidying: avoid repeated buzzphrases
    out = re.sub(r"(automation[ -]first|automation-first)\s+mindset", "automation", out, flags=re.I)

    return out.strip()


def tailor_summary(jd: str, job_title: str) -> str:
    profile = load_profile()
    keywords = extract_jd_keywords(jd, 8)
    top = ", ".join(keywords[:6]) if keywords else "Azure, AKS, CI/CD, DevSecOps"
    # Human-friendly summary template: concise, metric-first where available
    summary = f"{job_title if job_title else profile['title'].split('|')[0].strip()} with {profile['years_experience']} years' experience on Azure and AKS. Skilled in {top}. Built automation that reduced manual ops work and improved MTTR."
    summary = humanize_text(summary)
    return summary


def tailor_bullets(jd: str, max_bullets: int = 6) -> list[str]:
    profile = load_profile()
    bullets = profile["experience_highlights"].copy()

    def relevance(b: str) -> int:
        return sum(1 for k in extract_jd_keywords(jd, 20) if k.lower() in b.lower())

    bullets.sort(key=relevance, reverse=True)
    keywords = extract_jd_keywords(jd, 5)
    if keywords:
        opener = (
            f"Strong fit for this role with hands-on experience in {', '.join(keywords[:4])} in production Azure environments."
        )
        if opener not in bullets:
            bullets.insert(0, opener)

    # Humanize bullets: keep factual and concise
    bullets = [humanize_text(b) for b in bullets[:max_bullets]]
    return bullets


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

    cover = (
        f"I'm excited to apply for the {title} role at {company}. I have {profile['years_experience']} years' experience in cloud engineering and DevSecOps, and have worked with {top_skills} in production.\n\n"
        f"Your job emphasizes requirements that match my background, especially {hook}. At Amdocs, I reduced MTTR by 40% through AKS pod recovery automation, cut manual compliance effort via Python tooling, and improved monitoring coverage with Prometheus and Grafana.\n\n"
        f"I'm AZ-104 certified and have built open-source tools for Azure security auditing and cost governance. I'd welcome a chance to discuss how I can help {company}.\n\n"
        f"Thanks for your time — I look forward to speaking.\n\n"
        f"Best regards,\n"
        f"{profile['name']}\n"
        f"{profile['phone']} | {profile['email']}\n"
        f"{profile['linkedin']}"
    )

    cover = humanize_text(cover)
    return cover


def _replace_sections_from_base(base_doc: Document, jd: str, title: str, company: str) -> Document:
    """Create a new Document preserving base_doc layout but replacing specific sections.

    The function looks for well-known headings and replaces the content under them with tailored
    content while copying other paragraphs verbatim. Headings targeted:
      - PROFESSIONAL SUMMARY
      - RELEVANT EXPERIENCE HIGHLIGHTS
      - KEY SKILLS FOR THIS ROLE
      - CERTIFICATIONS
    """
    headings = [
        "PROFESSIONAL SUMMARY",
        "RELEVANT EXPERIENCE HIGHLIGHTS",
        "KEY SKILLS FOR THIS ROLE",
        "CERTIFICATIONS",
    ]

    def is_heading(text: str) -> bool:
        if not text:
            return False
        t = text.strip().upper()
        return any(h == t for h in headings)

    new = Document()
    # Copy normal style basic setup
    style = new.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    skip_until_next_heading = False
    current_heading = None
    for p in base_doc.paragraphs:
        text = p.text or ""
        if is_heading(text):
            # write the heading and the tailored content
            current_heading = text.strip().upper()
            new.add_paragraph(text)
            # insert tailored content for this heading
            if current_heading == "PROFESSIONAL SUMMARY":
                new.add_paragraph(humanize_text(tailor_summary(jd, title)))
            elif current_heading == "RELEVANT EXPERIENCE HIGHLIGHTS":
                for b in tailor_bullets(jd):
                    new.add_paragraph(b, style="List Bullet")
            elif current_heading == "KEY SKILLS FOR THIS ROLE":
                # start with extracted keywords; augmentation may follow
                kw = extract_jd_keywords(jd, 20)
                new.add_paragraph(", ".join(kw))
            elif current_heading == "CERTIFICATIONS":
                profile = load_profile()
                for c in profile["certifications"]:
                    new.add_paragraph(c, style="List Bullet")
            # set flag to skip original content that followed this heading
            skip_until_next_heading = True
            continue
        if skip_until_next_heading:
            # If we hit another heading-like paragraph, stop skipping
            if is_heading(text):
                skip_until_next_heading = False
                # this paragraph will be handled in next loop
                continue
            # otherwise skip original paragraph content
            # continue skipping until next known heading
            continue
        # Not a heading and not skipping: copy paragraph as-is
        new.add_paragraph(text)

    # Preserve sections' ordering; the new document now has tailored sections
    return new


def _ensure_ats_threshold(doc: Document, jd: str, min_score: float = 9.5) -> Document:
    """Ensure ATS score for jd_keywords in doc is at least min_score (out of 10).

    If score is low, augment the KEY SKILLS paragraph by appending missing keywords until
    the threshold is met or no keywords remain.
    """
    keywords = extract_jd_keywords(jd, 20)
    # compute current score
    text = _doc_text(doc)
    score = compute_ats_score(text, keywords)
    # If score already good and >= base resume score, return
    if score >= min_score:
        return doc

    # Find KEY SKILLS FOR THIS ROLE paragraph index in doc
    # We will append missing keywords to the first paragraph after that heading
    p_index = None
    for i, p in enumerate(doc.paragraphs):
        if (p.text or "").strip().upper() == "KEY SKILLS FOR THIS ROLE":
            p_index = i
            break
    if p_index is None or p_index + 1 >= len(doc.paragraphs):
        # Can't find a skills paragraph to augment; append at the end
        target_para = doc.add_paragraph()
    else:
        target_para = doc.paragraphs[p_index + 1]

    existing = (target_para.text or "").strip()
    existing_lower = existing.lower()
    missing = [k for k in keywords if k.lower() not in existing_lower]

    for k in missing:
        if k.lower() in existing_lower:
            continue
        if existing:
            existing += ", " + k
        else:
            existing = k
        # write back
        target_para.text = existing
        # recompute score
        score = compute_ats_score(_doc_text(doc), keywords)
        if score >= min_score:
            break

    return doc


def generate_tailored_docx(job: dict, output_path: Path | None = None) -> str:
    profile = load_profile()
    jd = job.get("description", "")
    title = job.get("title", "Cloud Engineer")
    company = job.get("company", "")

    # If a base DOCX exists, use it and replace targeted sections to preserve formatting
    if BASE_RESUME_PATH.exists():
        try:
            base_doc = Document(str(BASE_RESUME_PATH))
            base_text = _doc_text(base_doc)
            base_keywords = extract_jd_keywords(jd, 20)
            base_score = compute_ats_score(base_text, base_keywords)

            tailored_doc = _replace_sections_from_base(base_doc, jd, title, company)
            # Ensure tailored ATS score >= 9.5 and not below base_score
            min_required = max(9.5, base_score)
            tailored_doc = _ensure_ats_threshold(tailored_doc, jd, min_required)

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                tailored_doc.save(str(output_path))
                return output_path.name

            safe_name = re.sub(r"[^\w\-]", "_", f"{company}_{title}")[:40]
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"resume_{safe_name}_{ts}.docx"
            path = OUTPUT_DIR / filename
            OUTPUT_DIR.mkdir(exist_ok=True)
            tailored_doc.save(str(path))
            return filename
        except Exception as e:
            print(f"Base DOCX tailoring failed: {e}")
            # fallback to generated doc below

    # Fallback behavior: generate a new doc (existing behavior)
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
    doc.add_paragraph(humanize_text(tailor_summary(jd, title)))

    doc.add_paragraph("RELEVANT EXPERIENCE HIGHLIGHTS").runs[0].bold = True
    for b in tailor_bullets(jd):
        doc.add_paragraph(b, style="List Bullet")

    doc.add_paragraph("KEY SKILLS FOR THIS ROLE").runs[0].bold = True
    doc.add_paragraph(", ".join(extract_jd_keywords(jd, 20)))

    doc.add_paragraph("CERTIFICATIONS").runs[0].bold = True
    for c in profile["certifications"]:
        doc.add_paragraph(c, style="List Bullet")

    # Ensure ATS >= 9.5
    doc = _ensure_ats_threshold(doc, jd, 9.5)

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
