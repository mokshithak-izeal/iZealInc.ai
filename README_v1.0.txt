VERSION 1.0 - SAVED JOB REVIEW QUEUE

Apply this ON TOP OF the working v0.9 project.

Replace/add:
- app/database/jobs.py
- app/api/jobs.py
- static/js/app.js
- main.py

Do NOT replace/delete:
- .env, .venv
- app/agents, app/models, app/matching from v0.9
- templates, styles.css, resumes
- data/applications.json if it exists

Features:
- Every Analyze & Match Job result is persisted to data/jobs.json.
- Same non-empty LinkedIn URL updates its existing saved job instead of adding another duplicate.
- Job Matches shows a Saved Job Review Queue.
- Statuses available: NEW, REVIEW, SKIPPED, APPLIED, INTERVIEW, REJECTED, OFFER.
- Current UI buttons: Review, Skip, Applied.
- Queue shows title/company/location, score/decision/status, and up to 8 missing required skills.

Run:
python -m uvicorn main:app
Verify /api/health = 1.0.0.
Open http://127.0.0.1:8000/?v=100 and hard refresh.
Analyze resume once, then analyze jobs. Each result should appear in Saved Job Review Queue.
