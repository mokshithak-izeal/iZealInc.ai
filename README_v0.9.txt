V0.9 - CANONICAL SKILLS + EXPLICIT SCORING

Replace:
- app/matching/skill_normalizer.py
- app/matching/scorer.py
- static/js/app.js
- main.py

Keep all Gemini agents/prompts/models, .env, .venv, templates, data and resumes.

Key fixes:
- RESTful APIs canonicalizes to REST API.
- Azure service aliases normalized more consistently.
- CI/CD, SQL, NoSQL, monitoring, security and microservices may receive related 50% evidence when appropriate.
- Base scoring model: required skills 55, experience 20, role 15, preferred 5, location 5.
- If a JD omits preferred/location/etc., only specified/comparable categories are used; the UI now shows the effective normalized weights, so redistribution is explicit.
- Experience below an explicit minimum/maximum remains a hard fail.

Restart:
python -m uvicorn main:app
Verify /api/health is 0.9.0.
Open http://127.0.0.1:8000/?v=090 or hard refresh, analyze the same resume, and rerun the same JD.
