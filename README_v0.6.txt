VERSION 0.6.0 - LINKEDIN JD PARSER FIX

Changes:
- Stronger Gemini job prompt specifically for natural-language LinkedIn JDs.
- Required/preferred classification no longer depends on literal headings.
- Job schema now includes responsibilities and extraction notes.
- UI always shows the parsed job before the match.
- score=null displays "Match not calculated", never "null%".
- Keeps v0.5 matching safety: no free points for empty requirement categories.

Install:
Copy app/, static/js/app.js and main.py into the existing JobAgent folder and replace.
Keep .venv, .env, templates, styles.css, resumes, data and existing database files.

Run:
python -m uvicorn main:app

Verify:
http://127.0.0.1:8000/api/health -> version 0.6.0

Test the SAME JD that produced INSUFFICIENT_JOB_DATA in v0.5.
First inspect Parsed LinkedIn Job, especially Required skills and Preferred skills.
Only interpret the score after confirming that parsing is sensible.
