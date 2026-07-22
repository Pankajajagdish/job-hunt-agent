# Job Hunt Agent

Finds **DevOps / Kubernetes / Cloud / IAM** openings from the **last 24 hours**
(India or Remote), including **LinkedIn** via public guest search (no API keys),
**tailors your resume to each JD**, and writes a **cover letter per opening** —
runs on GitHub Actions, no PC needed.

| | |
|---|---|
| **Dashboard** | https://pankajajagdish.github.io/job-hunt-agent/ |
| **Repo** | https://github.com/Pankajajagdish/job-hunt-agent |

---

## What it does (the actual workflow)

For every matching job posted in the **last 24 hours**:

1. **Finds** DevOps, Kubernetes, Cloud, IAM openings (last 24h, India or Remote) from:
   **LinkedIn** (public guest search — no login/keys), Remotive, RemoteOK, Arbeitnow,
   Jobicy, Himalayas + optional Adzuna, JSearch, Google Jobs, RSS
2. **Scores** against your profile (`shared/resume_profile.json`)
3. **Generates tailored resume** (DOCX) — summary, bullets, and skills reordered for that JD
4. **Writes cover letter** — references the JD requirements, your skills, and metrics
5. **Publishes** everything to the dashboard + GitHub Issue (email alert)

---

## How to use (3 steps)

### 1. Run the agent
**Actions → Job Hunt Agent → Run workflow**  
(or wait — runs automatically every 6 hours)

### 2. Open your dashboard
https://pankajajagdish.github.io/job-hunt-agent/

For each job you get:
- **⬇ Tailored Resume** — DOCX customized for that JD
- **View / Copy Cover Letter** — ready to paste on apply form
- **Apply on Site** — opens the job posting

### 3. Apply
1. Download tailored resume  
2. Copy cover letter  
3. Open apply link → upload resume → paste cover letter → submit  
4. Close the GitHub Issue when done  

---

## Email alerts

**Watch** the repo → **All Activity**  
New jobs (40%+ match) create a GitHub Issue with:
- Full cover letter text
- Link to tailored resume DOCX
- Apply URL

---

## Customize profile

Edit `shared/resume_profile.json`:
- `target_roles`, `skills`, `experience_highlights`
- `exclude_keywords` (e.g. "10+ years")

---

## Optional secrets (more India jobs)

**Settings → Secrets → Actions**

| Secret | Purpose |
|--------|---------|
| `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` | India jobs, last 24h filter built-in |
| `RAPIDAPI_KEY` | JSearch — LinkedIn/Indeed aggregated |
| `SERPAPI_KEY` | Google Jobs (today filter) |

---

## Output files per job

```
docs/applications/{job_id}/
  Pankaja_Kulkarni_{JobTitle}_{Company}.docx   ← skills updated for this JD
  cover_letter.txt
  meta.json
```

---

**Pankaja Jagdish Kulkarni** — DevSecOps / Cloud Engineer
