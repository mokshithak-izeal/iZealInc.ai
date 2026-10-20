PHASE 3 - GOOGLE GEMINI AI RESUME INTELLIGENCE

1. Copy this package's app/, static/js/app.js and main.py into the existing JobAgent folder. Replace when prompted.
2. With .venv active, install the current Google Gen AI SDK:
   python -m pip install "google-genai<3.0.0"
3. Add to your existing .env (do not commit the real key):
   GOOGLE_API_KEY=your_real_key
   GEMINI_MODEL=gemini-2.5-flash
4. Restart:
   python -m uvicorn main:app --reload
5. Check http://127.0.0.1:8000/api/health -> version 0.3.0 and Google Gemini.
6. Upload a PDF/DOCX in Candidate and click Analyze Resume.

Notes:
- The raw resume text is sent to the configured Gemini API for AI extraction.
- The model is instructed to extract only resume-supported information.
- Structured output is validated with Pydantic.
- Deterministic skills are also calculated as debugging/signals but the UI displays Gemini contextual skills.
- Scanned PDFs still require OCR, which is not included yet.
