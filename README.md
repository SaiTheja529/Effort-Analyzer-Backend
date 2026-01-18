<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Effort Analyzer – Backend</title>
  <style>
    body {
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.6;
      color: #222;
      max-width: 1000px;
      margin: auto;
      padding: 24px;
    }
    h1, h2, h3 {
      color: #111;
      margin-top: 32px;
    }
    h1 {
      font-size: 32px;
      border-bottom: 2px solid #ddd;
      padding-bottom: 10px;
    }
    h2 {
      font-size: 24px;
      border-bottom: 1px solid #eee;
      padding-bottom: 6px;
    }
    h3 {
      font-size: 18px;
      margin-top: 20px;
    }
    ul {
      margin-left: 20px;
    }
    li {
      margin-bottom: 6px;
    }
    code, pre {
      background-color: #f6f8fa;
      padding: 6px 10px;
      border-radius: 4px;
      font-family: Consolas, monospace;
      font-size: 14px;
    }
    pre {
      overflow-x: auto;
      margin: 12px 0;
    }
    .section {
      margin-bottom: 32px;
    }
    .note {
      background-color: #f9f9f9;
      border-left: 4px solid #ccc;
      padding: 12px;
      margin-top: 12px;
    }
  </style>
</head>
<body>

<h1>🚀 Effort Analyzer – Backend</h1>

<div class="section">
  <h2>Features</h2>

  <h3>Effort-Based Contribution Analysis</h3>
  <p>
    Instead of relying only on raw commit counts, this system measures actual development effort.
    Each commit is evaluated using:
  </p>
  <ul>
    <li>Lines of code added</li>
    <li>Lines of code deleted</li>
  </ul>
  <p>
    This approach provides a fair and realistic understanding of how much work a developer has contributed.
  </p>

  <h3>GitHub Repository Integration</h3>
  <p>
    The backend integrates directly with GitHub using the GitHub REST API.
    Given a repository name, it automatically fetches:
  </p>
  <ul>
    <li>Repository metadata</li>
    <li>Commit history</li>
    <li>Contributors</li>
    <li>Programming languages used</li>
  </ul>
  <p>No manual data collection is required.</p>

  <h3>Developer-Wise Contribution Tracking</h3>
  <p>
    For each repository, individual developers are identified and tracked based on:
  </p>
  <ul>
    <li>Their commits</li>
    <li>Their effort score</li>
    <li>Their overall contribution</li>
  </ul>

  <h3>Commit-Level Analysis</h3>
  <p>
    Each commit is processed individually and stored with:
  </p>
  <ul>
    <li>Commit message</li>
    <li>Author</li>
    <li>Timestamp</li>
    <li>Lines added and deleted</li>
  </ul>
  <p>Duplicate commits are automatically ignored to maintain clean data.</p>

  <h3>Background Job Processing</h3>
  <p>
    Repository analysis runs as a background job, ensuring the API remains responsive.
    Once triggered, the analysis continues independently without blocking user requests.
  </p>

  <h3>Job Status & Progress Tracking</h3>
  <p>
    Every analysis request generates a unique job ID.
    Using this ID, users can track:
  </p>
  <ul>
    <li>Job status (queued, running, completed, failed)</li>
    <li>Current processing stage</li>
  </ul>

  <h3>Incremental Sync (Optimized Analysis)</h3>
  <p>
    The system remembers the last analyzed commit timestamp.
    On subsequent runs, only new commits are processed, which:
  </p>
  <ul>
    <li>Saves time</li>
    <li>Reduces GitHub API usage</li>
    <li>Improves performance</li>
  </ul>

  <h3>AI-Based Commit Understanding (Gemini Integration)</h3>
  <p>
    Each commit message is sent to Gemini AI to:
  </p>
  <ul>
    <li>Interpret the intent of the commit</li>
    <li>Generate a short, human-readable summary</li>
  </ul>

  <h3>AI-Generated Project Summary</h3>
  <p>
    Repository-level data is analyzed using Gemini AI to generate:
  </p>
  <ul>
    <li>High-level project explanation</li>
    <li>Project purpose and use case</li>
    <li>Simplified overview for recruiters or new developers</li>
  </ul>

  <h3>Automatic Tech Stack Detection</h3>
  <p>The system automatically detects:</p>
  <ul>
    <li>Programming languages used</li>
    <li>Their relative usage</li>
  </ul>

  <h3>GitHub OAuth Authentication</h3>
  <p>
    Secure GitHub OAuth authentication is supported without affecting commit analysis logic.
    Users can:
  </p>
  <ul>
    <li>Sign in using their GitHub account</li>
    <li>Authorize access securely via OAuth</li>
    <li>Fetch authenticated GitHub user details through APIs</li>
  </ul>

  <h3>Secure Credential Management</h3>
  <p>
    All sensitive credentials (GitHub tokens, OAuth secrets, Gemini API keys) are:
  </p>
  <ul>
    <li>Stored using environment variables</li>
    <li>Never exposed in the codebase</li>
  </ul>

  <h3>Rate-Limit & Failure Handling</h3>
  <p>The system safely handles:</p>
  <ul>
    <li>GitHub API rate limits</li>
    <li>Temporary API failures</li>
    <li>AI service downtime</li>
  </ul>

  <h3>Scalable & Asynchronous Backend Architecture</h3>
  <p>
    Built using FastAPI, the backend is fully asynchronous, high-performance,
    and designed to scale as usage grows.
  </p>
</div>

<div class="section">
  <h2>What Does a “Job” Mean?</h2>
  <p>
    In this project, a <strong>job</strong> simply means:
  </p>
  <p>
    One request to analyze a GitHub repository that runs in the background and takes time to complete.
  </p>
</div>

<div class="section">
  <h2>Local Setup & Run Instructions</h2>

  <h3>Clone the Repository</h3>
  <pre>git clone &lt;your-repository-url&gt;
cd effort-analyzer-backend</pre>

  <h3>Create & Activate Virtual Environment</h3>
  <pre>python3.11 -m venv .venv
source .venv/bin/activate</pre>

  <h3>Install Dependencies</h3>
  <pre>pip install -r requirements.txt</pre>

  <h3>Configure Environment Variables</h3>
  <pre>GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_api_key
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
DATABASE_URL=sqlite+aiosqlite:///./effort_analyzer.db</pre>

  <h3>Start the Backend Server</h3>
  <pre>uvicorn app.main:app --reload</pre>

  <p>Server runs at:</p>
  <pre>http://127.0.0.1:8000</pre>

  <h3>API Documentation</h3>
  <pre>http://127.0.0.1:8000/docs</pre>
</div>

<div class="section note">
  <strong>Notes:</strong>
  <ul>
    <li>Repository analysis runs in background jobs.</li>
    <li>Job progress is tracked using job IDs.</li>
    <li>GitHub OAuth can be tested via <code>/auth/github</code> endpoints.</li>
    <li>The backend is production-ready and fully asynchronous.</li>
  </ul>
</div>

</body>
</html>
