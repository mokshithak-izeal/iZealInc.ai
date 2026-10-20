JOBAGENT v1.6 - UI INTEGRATION
Prerequisite: working v1.5 backend.

This update intentionally does NOT replace the working app.js.
It adds v16_addon.js after app.js.

Features:
- Loads/saves Preferred Role, Preferred Location and Minimum Match via /api/preferences.
- Saved Job Review Queue on Job Matches.
- Queue filters: All, 80%+, and each lifecycle status.
- Sort: score, newest, company.
- Status buttons: Review, Applied, Interview, Offer, Skip, Rejected.
- Delete saved job.
- Applications page is generated from APPLIED/INTERVIEW/REJECTED/OFFER statuses.
- Dashboard cards use /api/jobs/dashboard.

INSTALL FROM JOBAGENT ROOT:
1. Extract this ZIP anywhere.
2. Copy the extracted static/js/v16_addon.js to JobAgent/static/js/v16_addon.js OR run:
   python <path-to-extracted-folder>/install_v16.py
   while your terminal is in the JobAgent project root.
3. If copying manually, add this before </body> in templates/index.html:
   <script src="/static/js/v16_addon.js?v=160"></script>
4. Restart: python -m uvicorn main:app
5. Open http://127.0.0.1:8000/?v=160 and Ctrl+F5.

SMOKE TEST:
- preferences survive refresh
- analyzed jobs appear in queue
- 80%+ filter works
- status changes survive refresh/server restart
- Applications reflects lifecycle status
- Dashboard counts change with statuses
