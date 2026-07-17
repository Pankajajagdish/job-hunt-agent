# Job Hunt Agent (GitHub-only)

Runs entirely on **your GitHub repo** — no PC server, no Android Studio.

| What | Where |
|------|--------|
| **Live job dashboard** | https://pankajajagdish.github.io/job-hunt-agent/ |
| **Push alerts** | GitHub Issues with label `job-alert` (email if you watch the repo) |
| **Agent runs** | GitHub Actions every 6 hours + manual trigger |

---

## Setup (one time, ~3 minutes)

### 1. Enable GitHub Pages

1. Open **Settings → Pages** on your repo
2. **Build and deployment → Source:** Deploy from a branch
3. **Branch:** `main` → folder **`/docs`** → Save

Dashboard URL: `https://pankajajagdish.github.io/job-hunt-agent/`

### 2. Watch repo for email alerts

1. Click **Watch** on the repo → **All Activity**
2. New matching jobs (45%+ score) open as **Issues** → GitHub emails you

### 3. Run the agent now

1. Go to **Actions** → **Job Hunt Agent** → **Run workflow**

Optional API keys (more jobs, especially India): **Settings → Secrets → Actions**

| Secret | Where to get |
|--------|----------------|
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | https://developer.adzuna.com/ (free) |
| `RAPIDAPI_KEY` | https://rapidapi.com/ (JSearch = LinkedIn/Indeed) |
| `SERPAPI_KEY` | https://serpapi.com/ (optional) |
| `RSS_FEED_URLS` | Comma-separated LinkedIn alert RSS URLs |

### 4. Customize profile

Edit `shared/resume_profile.json` → commit → next Action run uses it.

---

## Daily workflow (2 steps)

1. **Check email** or open the [dashboard](https://pankajajagdish.github.io/job-hunt-agent/) for new jobs  
2. Click **Apply Now** → apply on the company site → **Close the GitHub Issue** when done  

Target: 50 applications/day — track by closing issues or your own sheet.

---

## How it works

```
GitHub Actions (every 6h)
    → Fetch Remotive, RemoteOK, Arbeitnow (+ optional Adzuna/JSearch)
    → Score vs your resume profile
    → Update docs/jobs_feed.json (dashboard)
    → Open GitHub Issues for new high-score jobs
    → You get email notification
```

---

## Local backend + Android (optional)

If you also want the Android app or local API:

```bat
start_backend.bat
```

See `backend/` and `android-app/` folders. **GitHub-only mode does not require these.**

---

## Author

**Pankaja Jagdish Kulkarni** — DevSecOps / Cloud Engineer  
Portfolio: https://pankajajagdish.github.io
