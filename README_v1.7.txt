JOBAGENT v1.7 AUTOMATION LAB
Prerequisite: your working v1.6.2 project.

WHAT THIS DOES
1. Adds an ingestion endpoint for LinkedIn Job Alert content that you receive/export/copy into JobAgent.
2. Automatically deduplicates, parses with your existing Gemini JD agent, scores with your existing matcher, saves the job, and assigns:
   score >= threshold and eligible -> REVIEW
   otherwise -> SKIPPED
3. Adds local mock application portal at /mock-apply.
4. Stores mock submissions in data/mock_submissions.json.
5. Includes a helper that generates Playwright automation code targeting ONLY the local mock portal.

WHAT THIS DOES NOT DO
- It does not scrape linkedin.com.
- It does not log into LinkedIn.
- It does not automatically submit a LinkedIn application.

INSTALL
From your real JobAgent root:
python "<extracted-path>\install_v17.py"

Then ensure requirements include python-multipart for the mock upload form. If missing:
pip install python-multipart

Restart:
python -m uvicorn main:app

VERIFY
/api/health should report 1.7.0
/mock-apply should display the local test application form.

AUTOMATION INGEST ENDPOINT
POST /api/automation/linkedin-alert
Body example:
{
  "title": "Python Backend Developer",
  "job_url": "https://www.linkedin.com/jobs/view/...",
  "description": "complete job description",
  "candidate_profile": { ...the analyzed resume profile... },
  "preferred_location": "Bengaluru",
  "threshold": 80
}

Result auto_status is REVIEW or SKIPPED.
