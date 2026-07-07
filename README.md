**Local Research Paper Analyzer**

A local AI-powered research paper analyzer built with Python, Streamlit, Ollama, and PyMuPDF4LLM. The application extracts structured content from research PDFs, identifies meaningful academic sections, filters false headings, and prepares the document for local LLM-based summarization.

## Project Overview

Research papers use different layouts, fonts, heading styles, tables, page headers, and publisher formats. These differences can cause incorrect section detection during PDF analysis.

This project uses PyMuPDF4LLM to convert PDFs into structured Markdown and applies confidence-based rules to identify valid research-paper headings. It filters page numbers, tables, figures, publisher metadata, author information, corrupted text, and other false headings.

The application then recommends the most suitable document-processing mode:

* Section-heading mode
* Hybrid mode
* Chapter or report mode
* Fallback chunking mode

The project is designed to run locally using Ollama models, helping keep uploaded research documents private.

## Features

* Upload and process research PDFs locally
* Extract structured Markdown using PyMuPDF4LLM
* Detect academic headings and subsections
* Recover missed Roman- and Arabic-numbered headings
* Reject page markers, tables, figures, metadata, and numerical rows
* Identify heading hierarchy and parent-child relationships
* Merge small subsections into larger analysis units
* Recommend section-based or fallback chunking
* Support local LLM models through Ollama
* Generate structured research-paper summaries
* Export analysis results to Word format
* Download document-structure reports as JSON
* Compare multiple local LLM models for speed and output quality

## Architecture

```text
Research PDF
    |
    v
PyMuPDF4LLM Extraction
    |
    v
Structured Markdown
    |
    v
Heading Candidate Detection
    |
    v
Confidence Scoring and Filtering
    |
    +--> Reject false headings
    |
    +--> Keep structure-only headings
    |
    +--> Merge child subsections
    |
    v
Document Processing Mode
    |
    +--> Section-heading mode
    +--> Hybrid mode
    +--> Chapter/report mode
    +--> Fallback chunking mode
    |
    v
Local Ollama LLM
    |
    v
Structured Research Paper Analysis
    |
    v
Streamlit Display and Word Export
```

## Technology Stack

* Python
* Streamlit
* Ollama
* PyMuPDF
* PyMuPDF4LLM
* python-docx
* Requests
* Local open-source LLMs

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/VAbhinag/local-research-paper-analyzer.git
```

```powershell
cd local-research-paper-analyzer
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

## Ollama Model Setup

Install Ollama from the official Ollama website.

After installation, download a local model.

For faster processing:

```powershell
ollama pull llama3.2:1b
```

For improved summary quality:

```powershell
ollama pull qwen2.5:3b
```

Check installed models:

```powershell
ollama list
```

Test a model:

```powershell
ollama run llama3.2:1b
```

The current application supports locally installed Ollama models, including:

* Llama 3.2 1B
* Qwen 2.5 3B

## Running the Streamlit Application

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run the main application:

```powershell
streamlit run app.py
```

Run the PDF structure analyzer:

```powershell
streamlit run research_pdf_structure_analyzer.py
```

Streamlit will open the application in your browser.

The default local address is:

```text
http://localhost:8501
```

## Screenshots

Add project screenshots to a folder named:

```text
screenshots/
```

Example Markdown:

```markdown
![Research Paper Analyzer](screenshots/main-interface.png)

![Heading Detection](screenshots/heading-analysis.png)

![Generated Summary](screenshots/summary-output.png)
```

Recommended screenshots:

* Main PDF upload interface
* Model-selection menu
* Detected heading structure
* Confidence-scoring results
* Final research-paper summary
* Downloaded Word report

## Current Limitations

* PDF layouts differ significantly across publishers and document types.
* Some PDFs contain unusual font encoding that may produce corrupted text.
* PyMuPDF4LLM may classify visually prominent text as headings.
* Scanned PDFs without embedded text may require OCR support.
* Small local models may omit details or produce inaccurate summaries.
* Heading confidence rules may require fallback chunking for complex documents.
* Tables, mathematical formulas, and figures are not yet fully analyzed.
* Long documents may require additional processing time.
* Current hierarchy merging may still create too many analysis units for some papers.

## Future Improvements

* Add automatic document-type classification
* Improve parent-child heading hierarchy
* Merge nested subsections more consistently
* Add OCR support for scanned PDFs
* Add table and figure understanding
* Add citation extraction and reference mapping
* Compare model speed, memory usage, and summary quality
* Add configurable chunk sizes
* Add semantic search and question-answering
* Add retrieval-augmented generation
* Add batch processing for multiple research papers
* Add summary-quality evaluation metrics
* Add Docker deployment
* Add automated unit tests
* Improve Word-report formatting
* Add support for more Ollama models

## Privacy

The application is designed to run locally. Research PDFs and generated summaries do not need to be sent to an external cloud service when local Ollama models are used.

## Project Status

This project is an actively developed prototype. The current version supports local PDF extraction, academic-heading analysis, section planning, local LLM summarization, and downloadable reports.

## Author

Abhinag Vangala

GitHub: https://github.com/VAbhinag

## License

This project is available for educational and portfolio purposes.