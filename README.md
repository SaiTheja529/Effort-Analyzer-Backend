<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Effort Analyzer Backend</title>
  <style>
    body { font-family: Arial, Helvetica, sans-serif; line-height: 1.55; margin: 24px; color: #111; }
    h1, h2, h3 { margin-top: 22px; }
    code, pre { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; }
    pre { padding: 12px; overflow-x: auto; }
    ul { margin-top: 6px; }
    .section { margin-bottom: 18px; }
    .note { background: #fff7d6; padding: 10px 12px; border-left: 4px solid #f3c600; border-radius: 6px; }
  </style>
</head>
<body>

  <h1>Effort Analyzer Backend</h1>
  <p>
    FastAPI backend for the Effort Analyzer project.<br/>
    It analyzes GitHub repositories, scores commit effort, generates AI summaries,
    tracks developer trends, and serves account-specific history.
  </p>

  <div class="section">
    <h2>What this backend does</h2>
    <ol>
      <li>Takes a repository (<code>owner/repo</code>) from the frontend.</li>
      <li>Runs analysis in a background job.</li>
      <li>Pulls commit data from GitHub.</li>
      <li>Scores each commit using a hybrid scoring model.</li>
      <li>Stores results in SQLite via SQLAlchemy.</li>
      <li>Returns commits, rankings, trends, summaries, and history through APIs.</li>
    </ol>
  </div>

  <div class="section">
    <h2>Key features</h2>
    <ol>
      <li>
        <strong>Dual authentication</strong>
        <ul>
          <li>Local email/password auth (<code>/auth/register</code>, <code>/auth/login</code>, <code>/auth/me</code>)</li>
          <li>GitHub OAuth auth (<code>/auth/github/token</code>, <code>/auth/github/me</code>)</li>
        </ul>
      </li>

      <li>
        <strong>Account-specific data isolation</strong>
        <ul>
          <li>Jobs/history are tied to the logged-in actor (<code>owner_key</code>)</li>
          <li>Users only see and delete their own history</li>
        </ul>
      </li>

      <li>
        <strong>Async background analysis jobs</strong>
        <ul>
          <li>Analysis runs in background (non-blocking)</li>
          <li>Job lifecycle: <code>queued -&gt; running -&gt; succeeded/failed</code></li>
          <li>Progress is available via <code>/jobs/{job_id}</code></li>
        </ul>
      </li>

      <li>
        <strong>Reliable GitHub integration</strong>
        <ul>
          <li>Accepts repo in multiple formats (URL or <code>owner/repo</code>)</li>
          <li>Normalizes repo names</li>
          <li>Handles rate limits, retries, and API failures with clear errors</li>
        </ul>
      </li>

      <li>
        <strong>Commit-level storage with de-duplication</strong>
        <ul>
          <li>Stores commit SHA, message, author, timestamp, additions/deletions</li>
          <li>Skips duplicates (<code>repo_id + sha</code> unique)</li>
          <li>Supports incremental sync with <code>last_synced_at</code></li>
        </ul>
      </li>

      <li>
        <strong>Hybrid effort scoring (Effort v2)</strong>
        <ul>
          <li>Deterministic baseline score from code-change signals</li>
          <li>LLM rubric score from compact diff context</li>
          <li>Final score combines both for better balance</li>
          <li>If AI fails, deterministic fallback still returns a score</li>
        </ul>
      </li>

      <li>
        <strong>AI summaries + provider fallback</strong>
        <ul>
          <li>Primary provider: Gemini</li>
          <li>Fallback provider: Grok (xAI) when Gemini is unavailable</li>
          <li>Stores <code>score_source</code>, <code>score_confidence</code>, and short reason for transparency</li>
        </ul>
      </li>

      <li>
        <strong>Repository context + project explanation</strong>
        <ul>
          <li>Fetches and stores README excerpt, topics, and languages</li>
          <li>Generates high-level project explanation through AI</li>
        </ul>
      </li>

      <li>
        <strong>Insights APIs</strong>
        <ul>
          <li>Commits API with summaries and effort metadata</li>
          <li>Contributor rankings API</li>
          <li>Developer trends API (daily/weekly buckets)</li>
        </ul>
      </li>

      <li>
        <strong>History management</strong>
        <ul>
          <li>Delete a single history entry (<code>DELETE /jobs/{job_id}</code>)</li>
          <li>Delete all account history (<code>DELETE /jobs/history/all</code>)</li>
          <li>Export account-scoped data (<code>GET /data/export</code>)</li>
        </ul>
      </li>

      <li>
        <strong>Startup migration safety</strong>
        <ul>
          <li>Auto-creates tables</li>
          <li>Adds <code>jobs.owner_key</code> column/index if missing</li>
        </ul>
      </li>
    </ol>
  </div>

  <div class="section">
    <h2>Effort scoring in simple words</h2>
    <p>Each commit score is calculated in 3 layers:</p>
    <ol>
      <li>
        <strong>Deterministic baseline</strong>
        <ul>
          <li>Looks at additions, deletions, number of files touched, breadth of change, tests/docs impact, etc.</li>
        </ul>
      </li>
      <li>
        <strong>LLM rubric (optional)</strong>
        <ul>
          <li>Evaluates feature impact, code quality, code organization, maintainability, risk handling, and testing impact.</li>
        </ul>
      </li>
      <li>
        <strong>Final weighted score</strong>
        <ul>
          <li>Combines LLM score and deterministic score.</li>
          <li>If LLM fails (quota/network/provider issue), backend automatically falls back to deterministic only.</li>
        </ul>
      </li>
    </ol>

    <p>You also get:</p>
    <ul>
      <li><code>score_source</code> (where score came from)</li>
      <li><code>score_confidence</code> (trust level of score)</li>
      <li><code>score_reason</code> (short explanation)</li>
    </ul>
  </div>

  <div class="section">
    <h2>API overview</h2>

    <h3>Health</h3>
    <ul><li><code>GET /health</code></li></ul>

    <h3>Auth</h3>
    <ul>
      <li><code>POST /auth/register</code></li>
      <li><code>POST /auth/login</code></li>
      <li><code>GET /auth/me</code></li>
      <li><code>POST /auth/github/token</code></li>
      <li><code>GET /auth/github/me</code></li>
    </ul>

    <h3>Analysis and jobs</h3>
    <ul>
      <li><code>POST /analyze-repo</code></li>
      <li><code>GET /jobs/{job_id}</code></li>
      <li><code>DELETE /jobs/{job_id}</code></li>
      <li><code>DELETE /jobs/history/all</code></li>
    </ul>

    <h3>Insights</h3>
    <ul>
      <li><code>GET /commits?repo_full_name=owner/repo</code></li>
      <li><code>GET /contributors?repo_full_name=owner/repo</code></li>
      <li><code>GET /rankings?repo_full_name=owner/repo</code></li>
      <li><code>GET /rankings/trends?repo_full_name=owner/repo&amp;bucket=week&amp;days=84&amp;top_n=6</code></li>
    </ul>

    <h3>Repo context and explanation</h3>
    <ul>
      <li><code>POST /repo-context/fetch</code></li>
      <li><code>GET /repo-context?repo_full_name=owner/repo</code></li>
      <li><code>POST /repo-explain</code></li>
    </ul>

    <h3>Data export</h3>
    <ul>
      <li><code>GET /data/export</code></li>
    </ul>
  </div>

  <div class="section">
    <h2>Tech stack</h2>
    <ul>
      <li>FastAPI</li>
      <li>SQLAlchemy (async) + aiosqlite</li>
      <li>Pydantic + pydantic-settings</li>
      <li>httpx + tenacity</li>
      <li>pandas (rankings/trends processing)</li>
      <li>Gemini API + Grok (xAI) fallback support</li>
    </ul>
  </div>

  <div class="section">
    <h2>Local setup</h2>

    <h3>1) Create environment</h3>
    <pre><code>python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt</code></pre>

    <h3>2) Configure <code>.env</code></h3>
    <pre><code># App / DB
APP_NAME=Effort Analyzer API
LOG_LEVEL=INFO
DATABASE_URL=sqlite+aiosqlite:///./effort.db

# GitHub
GITHUB_TOKEN=your_github_pat
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret

# AI providers
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemma-3-4b-it
XAI_API_KEY=your_xai_key
XAI_MODEL=grok-3-fast-latest
XAI_BASE_URL=https://api.x.ai

# Local auth
AUTH_SECRET_KEY=replace_with_a_long_random_secret
AUTH_TOKEN_EXPIRE_MINUTES=10080

# Effort v2 controls
EFFORT_V2_ENABLED=true
EFFORT_V2_LLM_ENABLED=true
EFFORT_V2_MAX_FILES_FOR_LLM=12
EFFORT_V2_MAX_PATCH_CHARS=9000
EFFORT_V2_TIMEOUT_SECONDS=35</code></pre>

    <div class="note">
      <p><strong>Notes:</strong></p>
      <ul>
        <li>If Gemini is unavailable, Grok fallback is used when <code>XAI_API_KEY</code> is set.</li>
        <li>
          Use a real xAI key from <code>console.x.ai</code> for Grok fallback.
          Keys starting with <code>gsk_</code> are Groq keys and are not valid for xAI.
        </li>
      </ul>
    </div>

    <h3>3) Run the server</h3>
    <pre><code>uvicorn app.main:app --reload</code></pre>

    <ul>
      <li>API base: <code>http://127.0.0.1:8000</code></li>
      <li>Swagger docs: <code>http://127.0.0.1:8000/docs</code></li>
    </ul>
  </div>

  <div class="section">
    <h2>Typical flow</h2>
    <ol>
      <li>User logs in (local or GitHub OAuth).</li>
      <li>Frontend calls <code>POST /analyze-repo</code>.</li>
      <li>Backend creates a job and starts analysis in background.</li>
      <li>Frontend polls <code>GET /jobs/{job_id}</code>.</li>
      <li>On success, frontend reads commits, rankings, trends, and history APIs.</li>
    </ol>
  </div>

  <div class="section">
    <h2>Project structure (backend)</h2>
    <pre><code>app/
  core/           # config
  db/             # engine/session/base
  dependencies/   # auth dependency (current actor)
  models/         # repository, commit, developer, job, user, repo_context
  routers/        # REST endpoints
  schemas/        # request/response models
  services/       # GitHub, AI, scoring, analysis, job, auth services
  main.py         # FastAPI app + CORS + startup migrations</code></pre>
  </div>

  <div class="section">
    <h2>Troubleshooting</h2>
    <ol>
      <li>
        <strong>"AI unavailable" in frontend</strong>
        <ul>
          <li>Check <code>GEMINI_API_KEY</code> and/or <code>XAI_API_KEY</code>.</li>
          <li>Restart backend after <code>.env</code> changes.</li>
        </ul>
      </li>

      <li>
        <strong>GitHub 404/Not Found</strong>
        <ul>
          <li>Verify repo format is <code>owner/repo</code>.</li>
          <li>Ensure <code>GITHUB_TOKEN</code> has access for private repos.</li>
        </ul>
      </li>

      <li>
        <strong>Rate limit issues</strong>
        <ul>
          <li>GitHub and AI providers may throttle requests.</li>
          <li>Retry later or reduce commit limits.</li>
        </ul>
      </li>

      <li>
        <strong>Auth token errors</strong>
        <ul>
          <li>Ensure frontend sends <code>Authorization: Bearer &lt;token&gt;</code>.</li>
          <li>Clear local storage and login again if token is stale.</li>
        </ul>
      </li>
    </ol>
  </div>

</body>
</html>
