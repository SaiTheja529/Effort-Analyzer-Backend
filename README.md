🚀 Features – Effort Analyzer
🔹 Effort-Based Contribution Analysis

Instead of relying only on raw commit counts, I designed this system to measure actual development effort.
Each commit is analyzed based on:

Lines of code added

Lines of code deleted

This approach provides a fair and realistic evaluation of how much work a developer has contributed to a project.

🔹 GitHub Repository Integration

The application integrates directly with GitHub using the GitHub REST API.
By providing a repository name, the system automatically fetches:

Repository metadata

Commit history

Contributors

Programming languages used

No manual data collection is required.

🔹 Developer-Wise Contribution Tracking

For each repository, the system identifies individual developers and tracks:

Their commits

Their effort score

Their overall contribution

This makes it easy to compare and analyze contributions across team members.

🔹 Commit-Level Analysis

Each commit is processed and stored individually with:

Commit message

Author

Timestamp

Lines added and deleted

Duplicate commits are automatically ignored to ensure clean and accurate data.

🔹 Background Job Processing

Repository analysis runs as a background job, ensuring the API remains responsive.
Once an analysis is triggered, it continues independently without blocking user requests.

🔹 Job Status & Progress Tracking

Every analysis request generates a unique job ID.
Using this job ID, users can track:

Job status (queued, running, completed, failed)

Current progress stage (fetching commits, processing commits, etc.)

🔹 Incremental Sync (Optimized Analysis)

The system remembers the last analyzed commit timestamp.
On subsequent runs, it processes only new commits, which:

Saves time

Reduces GitHub API usage

Improves overall performance

🔹 AI-Based Commit Understanding (Gemini Integration)

Each commit message is sent to Gemini AI, which:

Interprets the intent of the commit

Generates a short, human-readable summary

This makes commit histories easier to understand, even for non-technical users.

🔹 AI-Generated Project Summary

Repository-level data is also analyzed using Gemini AI to generate:

A high-level project explanation

Project purpose and use case

A simplified overview for recruiters or new developers

This allows anyone to understand a project quickly without digging into the codebase.

🔹 Automatic Tech Stack Detection

The application automatically detects:

Programming languages used in the repository

Their relative usage

This provides instant visibility into the project’s technical stack.

🔹 GitHub OAuth Authentication (New Feature)

The backend supports secure GitHub OAuth authentication without affecting commit analysis logic.
Users can:

Sign in using their GitHub account

Authorize access securely using OAuth

Fetch authenticated GitHub user details via API

OAuth credentials (Client ID & Secret) are managed securely using environment variables.

🔹 Secure API Key & Credential Management

All sensitive credentials (GitHub tokens, OAuth secrets, Gemini API keys) are:

Stored using environment variables

Never exposed in the codebase

This ensures production-ready security standards.

🔹 Rate-Limit & Failure Handling

The system safely handles:

GitHub API rate limits

Temporary API failures

AI service downtime

Retries and graceful fallbacks ensure the system remains stable.

🔹 Scalable & Asynchronous Backend Architecture

Built using FastAPI, the backend is:

Fully asynchronous

High-performance

Easy to extend with new features

The architecture is designed to scale as usage grows.

📌 What Does a “Job” Mean in This Project?

In this Effort Analyzer project, a job simply means:

One request to analyze a GitHub repository that runs in the background and takes time to complete.

Nothing more complicated than that.

📌 Project Summary 

This project focuses on measuring real developer effort, not just activity metrics.
By combining GitHub data with AI-generated insights, it delivers a fair, meaningful, and human-readable analysis of open-source and team-based repositories.





🛠️ Local Setup & Run Instructions

Follow the steps below to run the backend locally.

1️⃣ Clone the Repository
git clone <your-repository-url>
cd effort-analyzer-backend

2️⃣ Create & Activate Virtual Environment
python3.11 -m venv .venv
source .venv/bin/activate


This ensures all dependencies are installed in an isolated environment.

3️⃣ Install Dependencies
pip install -r requirements.txt


All required backend libraries (FastAPI, SQLAlchemy, GitHub API, Gemini AI, etc.) will be installed.

4️⃣ Configure Environment Variables

Create a .env file and add the required keys:

GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_api_key
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
DATABASE_URL=sqlite+aiosqlite:///./effort_analyzer.db


For production, these values should be set securely in the deployment environment.

5️⃣ Start the Backend Server
uvicorn app.main:app --reload


The server will start at:

http://127.0.0.1:8000

6️⃣ API Documentation

Interactive API docs are available at:

http://127.0.0.1:8000/docs

📌 Notes

Repository analysis runs in background jobs, so responses remain fast.

Job progress can be tracked using the generated job ID.

GitHub OAuth authentication can be tested using the /auth/github endpoints.

The backend is fully asynchronous and production-ready.
