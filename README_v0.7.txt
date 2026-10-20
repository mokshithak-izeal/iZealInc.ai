VERSION 0.7.0 - SKILL NORMALIZATION

Copy app/matching/, static/js/app.js and main.py over your existing v0.6 project.
Keep .env, .venv, resumes, data, templates, prompts and Gemini agents.

New matching behavior:
- Python 3.x = Python (full match)
- RESTful APIs = REST API (full match)
- Microsoft Azure = Azure (full match)
- K8s = Kubernetes (full match)
- SQL can receive partial credit from SQL Server/PostgreSQL/MySQL/Azure SQL Database
- NoSQL can receive partial credit from MongoDB/Redis
- CI/CD can receive partial credit from Azure DevOps/Jenkins/GitHub Actions/Azure Pipelines
- Cloud monitoring tools can receive partial credit from Prometheus/Grafana/OpenTelemetry/Azure Monitor/Application Insights
- Broader related evidence gets 50% credit and is shown in yellow.
- Missing required skills reduce the score but no longer automatically force NOT_ELIGIBLE.
- Failing an explicit experience constraint remains NOT_ELIGIBLE.

Run:
python -m uvicorn main:app
Verify /api/health shows 0.7.0.
Retest the SAME LinkedIn JD and compare the new skill-by-skill output with v0.6.
