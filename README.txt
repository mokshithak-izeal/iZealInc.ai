V1.6.2 FIX
This version avoids v16_addon.js entirely. It patches templates/index.html directly, so static-file caching/path issues cannot prevent the UI from appearing.

From your existing JobAgent root:
python <extracted-path>\install_v162.py

Then verify in PowerShell:
Select-String -Path .\templates\index.html -Pattern JOBAGENT_V162_UI_PATCH

Restart:
python -m uvicorn main:app

Open:
http://127.0.0.1:8000/?v=162
Ctrl+F5

Expected immediately on Candidate:
Job Preferences / Preferred Role / Preferred Location / Minimum Match (%)

Browser console should contain:
JOBAGENT v1.6.2 UI PATCH LOADED
