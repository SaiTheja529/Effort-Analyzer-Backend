# Effort Analyzer Backend

FastAPI backend for the Effort Analyzer project.  
It analyzes GitHub repositories, scores commit effort, generates AI summaries, tracks developer trends, and serves account-specific history.

---

## What this backend does

1. Takes a repository (`owner/repo`) from the frontend.
2. Runs analysis in a background job.
3. Pulls commit data from GitHub.
4. Scores each commit using a hybrid scoring model.
5. Stores results in SQLite via SQLAlchemy.
6. Returns commits, rankings, trends, summaries, and history through APIs.

---

## Key features

1. **Dual authentication**
   - Local email/password auth (`/auth/register`, `/auth/login`, `/auth/me`)
   - GitHub OAuth auth (`/auth/github/token`, `/auth/github/me`)

2. **Account-specific data isolation**
   - Jobs/history are tied to the logged-in actor (`owner_key`)
   - Users only see and delete their own history

3. **Async background analysis jobs**
   - Analysis runs in background (non-blocking)
   - Job lifecycle: `queued -> running -> succeeded/failed`
   - Progress is available via `/jobs/{job_id}`

4. **Reliable GitHub integration**
   - Accepts repo in multiple formats (URL or `owner/repo`)
   - Normalizes repo names
   - Handles rate limits, retries, and API failures with clear errors

5. **Commit-level storage with de-duplication**
   - Stores commit SHA, message, author, timestamp, additions/deletions
   - Skips duplicates (`repo_id + sha` unique)
   - Supports incremental sync with `last_synced_at`

6. **Hybrid effort scoring (Effort v2)**
   - Deterministic baseline score from code-change signals
   - LLM rubric score from compact diff context
   - Final score combines both for better balance
   - If AI fails, deterministic fallback still returns a score

7. **AI summaries + provider fallback**
   - Primary provider: Gemini
   - Fallback provider: Grok (xAI) when Gemini is unavailable
   - Stores `score_source`, `score_confidence`, and short reason for transparency

8. **Repository context + project explanation**
   - Fetches and stores README excerpt, topics, and languages
   - Generates high-level project explanation through AI

9. **Insights APIs**
   - Commits API with summaries and effort metadata
   - Contributor rankings API
   - Developer trends API (daily/weekly buckets)

10. **History management**
   - Delete a single history entry (`DELETE /jobs/{job_id}`)
   - Delete all account history (`DELETE /jobs/history/all`)
   - Export account-scoped data (`GET /data/export`)

11. **Startup migration safety**
   - Auto-creates tables
   - Adds `jobs.owner_key` column/index if missing

---

## Effort scoring in simple words

Each commit score is calculated in 3 layers:

1. **Deterministic baseline**
   - Looks at additions, deletions, number of files touched, breadth of change, tests/docs impact, etc.
2. **LLM rubric (optional)**
   - Evaluates feature impact, code quality, organization, maintainability, risk handling, and testing impact.
3. **Final weighted score**
   - Combines LLM score and deterministic score.
   - If LLM fails (quota/network/provider issue), backend falls back to deterministic only.

You also get:
- `score_source` (where score came from)
- `score_confidence` (trust level of score)
- `score_reason` (short explanation)

---

## API overview

### Health
- `GET /health`

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/github/token`
- `GET /auth/github/me`

### Analysis and jobs
- `POST /analyze-repo`
- `GET /jobs/{job_id}`
- `DELETE /jobs/{job_id}`
- `DELETE /jobs/history/all`

### Insights
- `GET /commits?repo_full_name=owner/repo`
- `GET /contributors?repo_full_name=owner/repo`
- `GET /rankings?repo_full_name=owner/repo`
- `GET /rankings/trends?repo_full_name=owner/repo&bucket=week&days=84&top_n=6`

### Repo context and explanation
- `POST /repo-context/fetch`
- `GET /repo-context?repo_full_name=owner/repo`
- `POST /repo-explain`

### Data export
- `GET /data/export`

---

## Tech stack

- FastAPI
- SQLAlchemy (async) + aiosqlite
- Pydantic + pydantic-settings
- httpx + tenacity
- pandas (rankings/trends processing)
- Gemini API + Grok (xAI) fallback support

---

## Local setup

### 1) Create environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
