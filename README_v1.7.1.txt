JOBAGENT v1.7.1 - LINKEDIN JOB ALERT EMAIL IMPORTER
Prerequisite: working v1.7.

This adds a clean email-content ingestion boundary. It does NOT log in to LinkedIn or scrape linkedin.com.

INSTALL
From the real JobAgent root:
  python "<extracted-path>\install_v171.py"
Restart:
  python -m uvicorn main:app
Verify /api/health reports 1.7.1.

NEW ENDPOINT
POST /api/automation/linkedin-alert-email
{
  "subject":"LinkedIn Job Alert",
  "body":"raw HTML or plain-text content of the alert email",
  "candidate_profile": { ... },
  "preferred_location":"Bengaluru",
  "threshold":80
}

The endpoint:
- identifies LinkedIn /jobs/view/ links in the supplied email
- hands each unique alert job to the existing v1.7 processor
- de-duplicates
- runs Gemini JD parsing
- scores against candidate profile
- saves job
- score >= threshold & eligible -> REVIEW
- otherwise -> SKIPPED

EMAIL AUTOMATION OPTIONS
A separate authorized mailbox connector can call this endpoint. Keep mailbox authentication outside JobAgent itself. For Microsoft 365/Outlook, Microsoft Graph or Power Automate can supply the new-message content to this endpoint when deployed to a reachable URL.

IMPORTANT
LinkedIn alert emails often contain summaries rather than the full JD. This importer deliberately does not fetch LinkedIn pages. If the email contains only a short summary, the matcher should not be treated as equivalent to scoring the complete JD.
