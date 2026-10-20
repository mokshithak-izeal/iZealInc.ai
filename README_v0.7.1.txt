VERSION 0.7.1 - UI HOTFIX

Symptom fixed:
  Error: Cannot read properties of undefined (reading 'join')

Cause:
The v0.7 frontend could receive a response where an optional array/object was missing, then render it without a defensive default. The API request could succeed but the browser rendering step could throw.

Changes:
- Adds safeArray() for optional array fields.
- Makes chips(), list(), and skillRows() tolerant of undefined/null values.
- Makes score_breakdown rendering tolerant of a missing object.
- No matching logic or Gemini prompt changes.

Install over v0.7:
1. Copy static/js/app.js and main.py into your existing JobAgent folder and replace.
2. Keep everything else unchanged.
3. Restart: python -m uvicorn main:app
4. Verify /api/health reports 0.7.1.
5. In the browser press Ctrl+F5 to bypass the cached app.js.
6. Analyze the resume again and retest the same JD.
