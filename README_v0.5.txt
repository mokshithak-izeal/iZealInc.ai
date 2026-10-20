VERSION 0.5.0 - LINKEDIN MANUAL WORKFLOW

This update:
- Fixes the scoring bug: empty required/preferred skill lists no longer receive free points.
- Shows the parsed job structure before the score.
- Adds a LinkedIn job URL field.
- Adds Open on LinkedIn.
- Adds Mark as Applied and local JSON application history.
- Adds duplicate detection when the same non-empty LinkedIn URL is marked applied again.

LinkedIn note:
This version intentionally does not scrape LinkedIn or automate LinkedIn actions. Paste the job URL and job description manually, then open LinkedIn for the actual application.

INSTALL:
Copy app/, static/js/app.js and main.py over the existing JobAgent project. Replace existing files.
Keep your .venv, .env, templates, styles.css, resumes and existing prompt/model files.

RUN:
python -m uvicorn main:app

VERIFY:
http://127.0.0.1:8000/api/health -> version 0.5.0

TEST:
1. Analyze resume.
2. Job Matches.
3. Paste LinkedIn job URL and full JD.
4. Analyze & Match Job.
5. Inspect Parsed LinkedIn Job first.
6. Inspect match score.
7. Open on LinkedIn and apply manually.
8. Mark as Applied.
9. Open Applications to see history.
