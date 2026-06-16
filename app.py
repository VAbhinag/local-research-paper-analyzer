import re

import fitz
import ollama
import streamlit as st


st.set_page_config(
    page_title="Research Paper Analyzer",
    page_icon="📄",
)


COMMON_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "literature review",
    "related work",
    "theoretical framework",
    "conceptual framework",
    "research methodology",
    "methodology",
    "research methods",
    "methods",
    "materials and methods",
    "research design",
    "data collection",
    "data analysis",
    "results",
    "findings",
    "discussion",
    "results and discussion",
    "limitations",
    "implications",
    "recommendations",
    "future research",
    "future work",
    "conclusion",
    "conclusions",
    "references",
}


def clean_heading(line: str) -> str:
    """Remove numbering and punctuation from a possible heading."""

    cleaned = line.strip()

    cleaned = re.sub(
        r"^\s*(\d+(\.\d+)*|[IVXLC]+)[\.\)\s:-]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip(" .:-").lower()


def is_section_heading(line: str) -> bool:
    """Check whether a line looks like a research-paper heading."""

    stripped_line = line.strip()

    if not stripped_line or len(stripped_line) > 100:
        return False

    normalized = clean_heading(stripped_line)

    if normalized in COMMON_HEADINGS:
        return True

    numbered_heading_pattern = (
        r"^\s*\d+(\.\d+)*[\.\)\s:-]+"
        r"[A-Za-z][A-Za-z\s,&/-]{2,80}$"
    )

    return bool(re.match(numbered_heading_pattern, stripped_line))


def split_by_section_headings(text: str) -> list[dict]:
    """Split extracted text using detected section headings."""

    lines = text.splitlines()
    sections = []

    current_title = "Document beginning"
    current_lines = []

    for line in lines:
        if is_section_heading(line):
            existing_text = "\n".join(current_lines).strip()

            if existing_text:
                sections.append(
                    {
                        "title": current_title,
                        "text": existing_text,
                    }
                )

            current_title = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    remaining_text = "\n".join(current_lines).strip()

    if remaining_text:
        sections.append(
            {
                "title": current_title,
                "text": remaining_text,
            }
        )

    return sections


def split_long_section(
    text: str,
    part_size: int = 7000,
) -> list[str]:
    """Split only sections that are too large for one model request."""

    if len(text) <= part_size:
        return [text]

    parts = []
    start = 0

    while start < len(text):
        end = min(start + part_size, len(text))
        parts.append(text[start:end])
        start = end

    return parts


def summarize_section(
    title: str,
    text: str,
) -> str:
    """Summarize one detected paper section."""

    parts = split_long_section(text)
    part_summaries = []

    for part_number, part in enumerate(parts, start=1):
        prompt = f"""
Analyze this section of a research paper.

Section title: {title}
Section part: {part_number} of {len(parts)}

Provide a concise factual summary containing:

- Main purpose of this section
- Important arguments or concepts
- Methods, evidence, data, or examples mentioned
- Findings or conclusions mentioned
- Limitations or unclear information

Rules:
- Use only the supplied section text.
- Do not invent information.
- Do not create research questions that are not explicitly stated.
- Keep the response concise.

Section text:
{part}
"""

        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options={
                "temperature": 0.2,
                "num_ctx": 4096,
            },
        )

        part_summaries.append(
            response["message"]["content"]
        )

    return "\n\n".join(part_summaries)


def create_final_summary(
    section_summaries: list[dict],
) -> str:
    """Create one final report from section-based summaries."""

    combined_text = "\n\n".join(
        f"SECTION: {item['title']}\n{item['summary']}"
        for item in section_summaries
    )

    prompt = f"""
Create a structured analysis of the complete research paper using the
section summaries below.

Include:

1. Paper topic
2. Research problem
3. Purpose of the study
4. Explicit research questions or objectives
5. Theoretical or conceptual framework
6. Methodology
7. Data, participants, or study setting
8. Main findings
9. Conclusions
10. Limitations
11. Practical implications
12. Important concepts
13. Information not clearly available
14. Brief overall summary

Rules:
- Use only the supplied section summaries.
- Do not invent missing information.
- Do not convert general discussion points into research questions.
- State clearly when information is unavailable.
- Remove repetition.
- Use clear headings.

Section summaries:
{combined_text}
"""

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0.2,
            "num_ctx": 4096,
        },
    )

    return response["message"]["content"]


st.title("Research Paper Analyzer")
st.write(
    "Upload a research paper and generate a section-based summary locally."
)

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
)

if uploaded_file is not None:
    try:
        pdf_bytes = uploaded_file.read()

        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf",
        )

        page_texts = []

        for page in document:
            page_texts.append(page.get_text("text"))

        page_count = len(document)
        document.close()

        full_text = "\n".join(page_texts)

        st.success("PDF uploaded and processed successfully.")

        st.write(f"**File name:** {uploaded_file.name}")
        st.write(f"**Number of pages:** {page_count}")
        st.write(f"**Extracted characters:** {len(full_text):,}")

        if full_text.strip():
            detected_sections = split_by_section_headings(full_text)

            sections_to_analyze = [
                section
                for section in detected_sections
                if clean_heading(section["title"]) != "references"
            ]

            st.subheader("Detected sections")

            for section in sections_to_analyze:
                st.write(f"- {section['title']}")

            st.write(
                f"**Sections to analyze:** "
                f"{len(sections_to_analyze)}"
            )

            if st.button("Analyze full paper by section"):
                section_summaries = []

                progress_bar = st.progress(0)
                status_text = st.empty()

                for index, section in enumerate(
                    sections_to_analyze,
                    start=1,
                ):
                    status_text.write(
                        f"Analyzing section {index} of "
                        f"{len(sections_to_analyze)}: "
                        f"{section['title']}"
                    )

                    summary = summarize_section(
                        title=section["title"],
                        text=section["text"],
                    )

                    section_summaries.append(
                        {
                            "title": section["title"],
                            "summary": summary,
                        }
                    )

                    progress = int(
                        (
                            index
                            / (len(sections_to_analyze) + 1)
                        )
                        * 100
                    )

                    progress_bar.progress(progress)

                status_text.write(
                    "Creating the final section-based report..."
                )

                final_summary = create_final_summary(
                    section_summaries
                )

                progress_bar.progress(100)
                status_text.success(
                    "Section-based paper analysis complete."
                )

                st.subheader("Full Research Paper Analysis")
                st.markdown(final_summary)

                st.subheader("Individual Section Summaries")

                for item in section_summaries:
                    with st.expander(item["title"]):
                        st.markdown(item["summary"])

        else:
            st.warning(
                "No selectable text was found. "
                "The PDF may contain scanned images."
            )

    except Exception as error:
        st.error(f"Unable to process the request: {error}")