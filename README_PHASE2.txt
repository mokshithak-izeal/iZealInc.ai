PHASE 2 UPDATE - Resume Analyzer

Copy these files/folders over your existing JobAgent folder and replace when prompted:
- main.py
- app/api/resumes.py
- app/extractors/resume_extractor.py
- app/api/__init__.py
- app/extractors/__init__.py
- static/js/app.js

No new pip packages are required because the starter requirements already include:
- python-multipart
- pymupdf
- python-docx

Restart the server:
  python -m uvicorn main:app --reload

Test:
1. Open http://127.0.0.1:8000
2. Candidate -> Choose PDF or DOCX -> Analyze Resume
3. The UI should populate candidate name (best effort), experience (when explicitly stated), and recognized skills.
4. API docs are available at http://127.0.0.1:8000/docs

Known limitation:
Scanned/image-only PDFs are rejected with a message saying OCR is required. OCR is not implemented in this phase.
