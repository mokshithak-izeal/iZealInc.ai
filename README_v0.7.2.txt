VERSION 0.7.2 - RENDER FIX

The previous hotfix did not cover every .join() path in app.js. This update adds safe formatting for score_breakdown and defensive defaults for the job/match response objects.

Replace ONLY:
  static/js/app.js
  main.py

Then:
  python -m uvicorn main:app

Verify:
  http://127.0.0.1:8000/api/health
  version must be 0.7.2

IMPORTANT browser step:
  Open DevTools (F12) > Network > check Disable cache, then Ctrl+F5.
  Or open the UI in a fresh InPrivate/Incognito window.

Then analyze the resume and test the same JD again.
