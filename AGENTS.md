# AGENTS.md

## Project Overview

This is a local Streamlit app for analyzing research PDFs. It uses PyMuPDF and PyMuPDF4LLM for extraction and structure detection, then supports local Ollama-based summarization so documents can stay on the user's machine.

## How To Set Up And Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

For the structure-analysis test app:

```powershell
streamlit run research_pdf_structure_analyzer.py
```

## Project Structure

- `app.py`: Main Streamlit workflow for PDF upload, text extraction, section splitting, and Ollama summarization.
- `research_pdf_structure_analyzer.py`: Experimental structure analyzer for PyMuPDF4LLM Markdown extraction, heading scoring, hierarchy planning, and JSON report export.

## Conventions And Boundaries

- Keep document processing local; do not add cloud upload, hosted LLM, telemetry, or external document-processing services without explicit user direction.
- Preserve the prototype-friendly Streamlit style unless the user asks for a larger architecture change.
- Prefer focused changes to heading detection, chunking, summarization prompts, or export behavior over broad refactors.
- Treat PDFs as potentially sensitive user documents and avoid logging extracted text unnecessarily.
