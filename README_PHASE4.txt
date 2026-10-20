PHASE 4 - NAME FIX + JOB DESCRIPTION MATCHING

WHAT CHANGED
1. Resume prompt moved to app/agents/prompts.py so it is easy to view/edit.
2. Candidate-name instruction now requires the complete name exactly as shown in the resume header/contact section.
3. Added a Gemini job-description parser.
4. Added deterministic matching code in app/matching/scorer.py.
5. After resume analysis, Job Matches becomes a paste-and-test screen.

COPY
Copy app/, static/js/app.js and main.py over the existing JobAgent project and replace existing files.
KEEP your existing .env, .venv, templates, styles.css and resume files.

RUN
python -m uvicorn main:app

VERIFY
http://127.0.0.1:8000/api/health should report version 0.4.0.
Analyze the resume again. The name should now be requested as the complete header/contact name.
Then open Job Matches, paste a job description, and click Analyze & Match Job.

IMPORTANT MATCHING NOTE
This first scorer treats any missing explicitly required skill as NOT_ELIGIBLE. The score is still shown for debugging. We should tune this rule with real job descriptions before automating applications.
