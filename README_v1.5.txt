JOBAGENT v1.5 - COMPLETE BACKEND WORKFLOW
Apply on top of your CURRENT WORKING v0.9/v1.0 project.

Replace/add:
  app/database/preferences.py
  app/database/jobs.py
  app/api/preferences.py
  app/api/jobs.py
  main.py

IMPORTANT: I intentionally did NOT replace your working static/js/app.js this time because earlier frontend replacements caused cache/version confusion. v15_addon.js contains optional browser helper functions only. Keep the working app.js.

Completed backend features:
- persisted candidate preferences
- saved analyzed jobs
- duplicate update by non-empty LinkedIn URL
- lifecycle statuses NEW/REVIEW/SKIPPED/APPLIED/INTERVIEW/REJECTED/OFFER
- delete job endpoint
- dashboard metrics endpoint
- restart-safe JSON persistence

Existing working features retained:
- Gemini resume extraction
- Gemini JD extraction
- v0.9 canonical/related matching
- LinkedIn manual URL/JD workflow

Endpoints:
GET/PUT /api/preferences
POST /api/jobs/analyze-match
GET /api/jobs/queue
PATCH /api/jobs/queue/{id}/status
DELETE /api/jobs/queue/{id}
GET /api/jobs/dashboard
GET /api/health

Not included by design: LinkedIn scraping/browser bots/auto-apply; automatic external job discovery without an authorized source API; production multi-user auth/database.

Run:
python -m uvicorn main:app
Verify /api/health = 1.5.0.
