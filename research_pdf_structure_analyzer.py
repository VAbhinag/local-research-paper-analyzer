import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf
import pymupdf4llm
import streamlit as st


st.set_page_config(
    page_title="Research PDF Structure Analyzer",
    page_icon="📄",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CORE_ACADEMIC_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "theoretical background",
    "conceptual background",
    "literature review",
    "related work",
    "related works",
    "research methodology",
    "methodology",
    "methods",
    "materials and methods",
    "research method",
    "research methods",
    "research design",
    "data collection",
    "data analysis",
    "results",
    "findings",
    "discussion",
    "discussion of findings",
    "results and discussion",
    "limitations",
    "implications",
    "recommendations",
    "future work",
    "future research",
    "conclusion",
    "conclusions",
}

STRUCTURE_ONLY_HEADINGS = {
    "keywords",
    "key words",
    "article history",
    "references",
    "bibliography",
    "acknowledgement",
    "acknowledgements",
    "acknowledgment",
    "acknowledgments",
    "biography",
    "biographies",
    "appendix",
    "appendices",
    "terminology",
    "credit authorship contribution statement",
    "author contributions",
    "declaration of competing interest",
    "declaration of competing interests",
    "conflict of interest",
    "conflicts of interest",
    "funding",
    "data availability",
    "data availability statement",
}

FRONT_MATTER_PHRASES = {
    "academic editor",
    "corresponding author",
    "publisher's note",
    "article history",
    "received",
    "revised",
    "accepted",
    "published",
    "citation",
    "copyright",
    "licensee",
    "peer-review under responsibility",
    "available online",
    "contents lists available",
    "journal homepage",
    "extended author information",
}

SENTENCE_STARTERS = {
    "the",
    "this",
    "these",
    "those",
    "our",
    "we",
    "it",
    "there",
    "a",
    "an",
    "as",
    "because",
    "based",
    "when",
    "while",
    "where",
    "which",
    "that",
}

PARENT_MERGE_PREFIXES = (
    "(i)",
    "(ii)",
    "(iii)",
    "(iv)",
    "(v)",
    "(vi)",
    "a)",
    "b)",
    "c)",
    "d)",
    "e)",
)


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_markdown_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract structured Markdown from an uploaded PDF."""

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = Path(temp_file.name)

        with pymupdf.open(temp_path) as document:
            page_count = len(document)

        markdown_text = pymupdf4llm.to_markdown(
            str(temp_path),
            show_progress=False,
        )

        return markdown_text, page_count

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


# ---------------------------------------------------------------------------
# Text normalization and pattern checks
# ---------------------------------------------------------------------------

def strip_markdown(text: str) -> str:
    """Remove Markdown syntax that should not appear in heading labels."""

    cleaned = text.strip()
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = cleaned.replace("`", "").replace("~", "")
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" \t-–—:;|")


def normalize_for_matching(text: str) -> str:
    """Normalize heading text while preserving meaningful words."""

    cleaned = strip_markdown(text)

    cleaned = re.sub(
        r"^\s*(?:\d+(?:\.\d+)*\.?|[IVXLCDM]+\.)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^\s*[a-z]\)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^\s*\([ivxlcdm]+\)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return re.sub(r"\s+", " ", cleaned).lower().strip()


def corrupted_character_ratio(text: str) -> float:
    if not text:
        return 1.0

    suspicious = sum(
        1
        for character in text
        if character in {"�", "□", "■", "�"}
    )

    return suspicious / len(text)


def is_page_marker(text: str, page_count: int) -> bool:
    """Reject page headers such as '2 of 36' or 'Page 4 of 18'."""

    cleaned = strip_markdown(text)

    patterns = [
        rf"^\s*(?:page\s*)?\d+\s+of\s+{page_count}\s*$",
        r"^\s*(?:page\s*)?\d+\s+of\s+\d+\s*$",
        r"^\s*\d+\s*/\s*\d+\s*$",
    ]

    return any(
        re.match(pattern, cleaned, flags=re.IGNORECASE)
        for pattern in patterns
    )


def is_caption_or_table_label(text: str) -> bool:
    """Reject figure, table, chart, and photo captions as section headings."""

    cleaned = strip_markdown(text)

    return bool(
        re.match(
            r"^\s*(?:fig(?:ure)?|table|chart|photo|scheme|algorithm)"
            r"\s*\.?\s*\d+[A-Za-z]?(?:\s*[:.\-–—].*)?$",
            cleaned,
            flags=re.IGNORECASE,
        )
    )


def is_numeric_or_code_row(text: str) -> bool:
    """Reject table values, measurements, model codes, and result rows."""

    cleaned = strip_markdown(text)

    if cleaned.count("|") >= 2:
        return True

    if re.fullmatch(
        r"[A-Za-z]{0,5}\d+[A-Za-z0-9._/\-]*",
        cleaned,
    ):
        return True

    if re.fullmatch(
        r"(?:[A-Za-z0-9]{1,8}\|){2,}[A-Za-z0-9.]+",
        cleaned,
    ):
        return True

    if re.fullmatch(
        r"\d+(?:\.\d+)?\s*(?:GHz|MHz|GB|MB|KB|ms|s|sec|seconds|%)",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return True

    letters = sum(character.isalpha() for character in cleaned)
    digits = sum(character.isdigit() for character in cleaned)

    if digits >= 4 and letters <= 4:
        return True

    return False


def is_metadata(text: str) -> bool:
    """Identify publisher, author, journal, affiliation, and copyright metadata."""

    cleaned = strip_markdown(text)
    lowered = cleaned.lower()

    if any(phrase in lowered for phrase in FRONT_MATTER_PHRASES):
        return True

    if "@" in cleaned or re.search(r"\bhttps?://|\bwww\.", lowered):
        return True

    if re.search(
        r"\b(?:doi|issn|isbn|volume|vol\.|issue)\b",
        lowered,
    ):
        return True

    if re.search(
        r"\b(?:university|department|faculty|institute|college|school)\b",
        lowered,
    ):
        return True

    if re.search(
        r"\b(?:journal|proceedings|scienceDirect|springer|elsevier|mdpi|ieee)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return True

    if re.search(
        r"(?:©|\bcopyright\b|\$\d+(?:\.\d{2})?)",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return True

    return False


def numbering_info(text: str) -> dict[str, Any]:
    """Return numbering style, depth, and label for a candidate heading."""

    cleaned = strip_markdown(text)

    arabic = re.match(
        r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+)$",
        cleaned,
    )

    if arabic:
        label = arabic.group(1)
        return {
            "style": "arabic",
            "label": label,
            "depth": label.count(".") + 1,
            "body": arabic.group(2).strip(),
        }

    roman = re.match(
        r"^\s*([IVXLCDM]+)\.\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )

    if roman:
        return {
            "style": "roman",
            "label": roman.group(1).upper(),
            "depth": 1,
            "body": roman.group(2).strip(),
        }

    lettered = re.match(
        r"^\s*([a-z])[\).]\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )

    if lettered:
        return {
            "style": "lettered",
            "label": lettered.group(1).lower(),
            "depth": 3,
            "body": lettered.group(2).strip(),
        }

    parenthetical_roman = re.match(
        r"^\s*\(([ivxlcdm]+)\)\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )

    if parenthetical_roman:
        return {
            "style": "parenthetical",
            "label": parenthetical_roman.group(1).lower(),
            "depth": 4,
            "body": parenthetical_roman.group(2).strip(),
        }

    chapter = re.match(
        r"^\s*chapter\s+(\d+)\b(.*)$",
        cleaned,
        flags=re.IGNORECASE,
    )

    if chapter:
        return {
            "style": "chapter",
            "label": chapter.group(1),
            "depth": 1,
            "body": cleaned,
        }

    return {
        "style": "none",
        "label": "",
        "depth": 2,
        "body": cleaned,
    }


def looks_like_sentence_fragment(text: str) -> bool:
    """Identify ordinary sentence fragments misclassified as headings."""

    cleaned = strip_markdown(text)
    words = cleaned.split()

    if not words:
        return True

    first_word = re.sub(r"[^A-Za-z]", "", words[0]).lower()

    if first_word in SENTENCE_STARTERS and len(words) >= 4:
        return True

    if len(words) > 16:
        return True

    if cleaned.endswith((".", "?", "!", ";", ",")):
        return True

    common_predicates = (
        " refers to ",
        " is defined as ",
        " are defined as ",
        " means that ",
        " was conducted ",
        " were conducted ",
        " has been ",
        " have been ",
        " will be ",
        " can be ",
        " should be ",
    )

    lowered = f" {cleaned.lower()} "

    return any(predicate in lowered for predicate in common_predicates)


def title_style_ratio(text: str) -> float:
    words = [
        re.sub(r"[^A-Za-z]", "", word)
        for word in strip_markdown(text).split()
    ]
    words = [word for word in words if word]

    if not words:
        return 0.0

    title_words = sum(
        word[0].isupper() or word.isupper()
        for word in words
    )

    return title_words / len(words)


# ---------------------------------------------------------------------------
# Candidate extraction and scoring
# ---------------------------------------------------------------------------

def can_recover_unmarked_heading(
    line: str,
    page_count: int,
) -> bool:
    """Conservatively recover headings missed by PyMuPDF4LLM."""

    candidate = strip_markdown(line)

    if not candidate or len(candidate) > 120:
        return False

    if candidate.startswith(("-", "*", "+", ">", "|", "```")):
        return False

    if is_page_marker(candidate, page_count):
        return False

    if is_caption_or_table_label(candidate):
        return False

    if is_numeric_or_code_row(candidate):
        return False

    if is_metadata(candidate):
        return False

    if corrupted_character_ratio(candidate) > 0.10:
        return False

    info = numbering_info(candidate)

    if info["style"] in {"arabic", "roman", "chapter"}:
        if looks_like_sentence_fragment(info["body"]):
            return False
        return len(info["body"].split()) <= 14

    normalized = normalize_for_matching(candidate)

    if normalized in CORE_ACADEMIC_HEADINGS:
        return True

    letters = [character for character in candidate if character.isalpha()]

    if letters:
        uppercase_ratio = (
            sum(character.isupper() for character in letters)
            / len(letters)
        )

        if (
            uppercase_ratio >= 0.90
            and 1 <= len(candidate.split()) <= 8
            and not looks_like_sentence_fragment(candidate)
        ):
            return True

    return False


def extract_candidates(
    markdown_text: str,
    page_count: int,
) -> list[dict[str, Any]]:
    """Extract PyMuPDF4LLM headings and conservatively recovered headings."""

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()

    for line_number, raw_line in enumerate(
        markdown_text.splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        markdown_match = re.match(
            r"^(#{1,6})\s+(.+?)\s*$",
            line,
        )

        if markdown_match:
            title = strip_markdown(markdown_match.group(2))
            key = (line_number, title.lower())

            if key not in seen:
                candidates.append(
                    {
                        "title": title,
                        "line_number": line_number,
                        "markdown_level": len(markdown_match.group(1)),
                        "source": "PyMuPDF4LLM",
                    }
                )
                seen.add(key)

            continue

        if can_recover_unmarked_heading(line, page_count):
            title = strip_markdown(line)
            key = (line_number, title.lower())

            if key not in seen:
                candidates.append(
                    {
                        "title": title,
                        "line_number": line_number,
                        "markdown_level": 2,
                        "source": "Recovered",
                    }
                )
                seen.add(key)

    return candidates


def score_candidate(
    candidate: dict[str, Any],
    page_count: int,
) -> dict[str, Any]:
    """Assign confidence, action, reason, and hierarchy to a heading."""

    title = strip_markdown(candidate["title"])
    normalized = normalize_for_matching(title)
    info = numbering_info(title)

    score = 0
    reasons: list[str] = []

    if candidate["source"] == "PyMuPDF4LLM":
        score += 3
        reasons.append("layout heading")
    else:
        score += 1
        reasons.append("recovered pattern")

    if info["style"] in {"arabic", "roman", "chapter"}:
        score += 3
        reasons.append("structured numbering")

    if normalized in CORE_ACADEMIC_HEADINGS:
        score += 4
        reasons.append("known academic heading")

    if normalized in STRUCTURE_ONLY_HEADINGS:
        score += 3
        reasons.append("known structural heading")

    word_count = len(title.split())

    if 1 <= word_count <= 12:
        score += 1
        reasons.append("short heading length")

    if title_style_ratio(title) >= 0.50:
        score += 1
        reasons.append("title-style capitalization")

    # Hard rejection rules
    if is_page_marker(title, page_count):
        return {
            **candidate,
            "title": title,
            "normalized": normalized,
            "score": -10,
            "action": "reject",
            "reason": "page marker",
            "depth": info["depth"],
        }

    if is_caption_or_table_label(title):
        return {
            **candidate,
            "title": title,
            "normalized": normalized,
            "score": -10,
            "action": "reject",
            "reason": "figure/table caption",
            "depth": info["depth"],
        }

    if is_numeric_or_code_row(title):
        return {
            **candidate,
            "title": title,
            "normalized": normalized,
            "score": -10,
            "action": "reject",
            "reason": "numeric/code/table row",
            "depth": info["depth"],
        }

    if corrupted_character_ratio(title) > 0.10:
        return {
            **candidate,
            "title": title,
            "normalized": normalized,
            "score": -10,
            "action": "reject",
            "reason": "corrupted extraction",
            "depth": info["depth"],
        }

    if is_metadata(title):
        return {
            **candidate,
            "title": title,
            "normalized": normalized,
            "score": -8,
            "action": "reject",
            "reason": "publisher/author metadata",
            "depth": info["depth"],
        }

    if looks_like_sentence_fragment(title) and info["style"] == "none":
        score -= 5
        reasons.append("sentence-like fragment")

    if word_count > 16:
        score -= 3
        reasons.append("too long")

    if normalized in STRUCTURE_ONLY_HEADINGS:
        action = "structure-only"
        reason = ", ".join(reasons)
    elif info["style"] in {"lettered", "parenthetical"}:
        action = "merge-with-parent"
        reason = "small component/list subsection"
    elif title.lower().startswith(PARENT_MERGE_PREFIXES):
        action = "merge-with-parent"
        reason = "small component/list subsection"
    elif score >= 5:
        action = "analyze"
        reason = ", ".join(reasons)
    elif score >= 3:
        action = "merge-with-parent"
        reason = ", ".join(reasons)
    else:
        action = "reject"
        reason = ", ".join(reasons) or "low confidence"

    return {
        **candidate,
        "title": title,
        "normalized": normalized,
        "score": score,
        "action": action,
        "reason": reason,
        "depth": info["depth"],
        "numbering_style": info["style"],
    }


def remove_duplicates(
    evaluated: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove repeated headings while preserving the first useful instance."""

    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in evaluated:
        key = (item["normalized"], item["action"])

        if key in seen and item["action"] != "reject":
            continue

        seen.add(key)
        output.append(item)

    return output


# ---------------------------------------------------------------------------
# Hierarchy and analysis plan
# ---------------------------------------------------------------------------

def attach_parent_titles(
    evaluated: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assign parent titles using numbering depth and document order."""

    stack: dict[int, str] = {}
    output: list[dict[str, Any]] = []

    for item in evaluated:
        current = dict(item)
        depth = max(1, min(int(current.get("depth", 2)), 6))

        if current["action"] == "reject":
            current["parent"] = ""
            output.append(current)
            continue

        parent = ""

        for candidate_depth in range(depth - 1, 0, -1):
            if candidate_depth in stack:
                parent = stack[candidate_depth]
                break

        current["parent"] = parent

        if current["action"] in {
            "analyze",
            "merge-with-parent",
            "structure-only",
        }:
            stack[depth] = current["title"]

            for deeper_depth in list(stack):
                if deeper_depth > depth:
                    del stack[deeper_depth]

        output.append(current)

    return output


def build_analysis_units(
    evaluated: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a practical section plan for the future summarizer."""

    units: list[dict[str, Any]] = []
    last_analyze_index: int | None = None

    for item in evaluated:
        if item["action"] == "analyze":
            units.append(
                {
                    "heading": item["title"],
                    "children": [],
                    "line_number": item["line_number"],
                }
            )
            last_analyze_index = len(units) - 1

        elif item["action"] == "merge-with-parent":
            if last_analyze_index is not None:
                units[last_analyze_index]["children"].append(
                    item["title"]
                )

    return units


def assess_structure_quality(
    evaluated: list[dict[str, Any]],
    page_count: int,
) -> dict[str, Any]:
    """Recommend section mode, chapter mode, or fallback chunking."""

    counts = Counter(item["action"] for item in evaluated)
    analyze_count = counts["analyze"]
    accepted_count = (
        counts["analyze"]
        + counts["merge-with-parent"]
        + counts["structure-only"]
    )
    reject_count = counts["reject"]

    accepted_density = accepted_count / max(page_count, 1)
    rejection_ratio = reject_count / max(len(evaluated), 1)

    has_chapter = any(
        item.get("numbering_style") == "chapter"
        and item["action"] != "reject"
        for item in evaluated
    )

    if page_count >= 50 or has_chapter:
        mode = "chapter/report mode"
        explanation = (
            "Use chapter boundaries and page-group chunks inside chapters."
        )
    elif analyze_count < 2:
        mode = "fallback chunking mode"
        explanation = (
            "Too few reliable sections; use paragraph-aware page chunks."
        )
    elif accepted_density > 3.0:
        mode = "hybrid mode"
        explanation = (
            "Heading density is high; keep major sections and merge small "
            "subsections before summarization."
        )
    elif rejection_ratio > 0.45:
        mode = "hybrid fallback mode"
        explanation = (
            "Many candidates were rejected; combine trusted headings with "
            "page-aware chunks."
        )
    else:
        mode = "section-heading mode"
        explanation = (
            "Use the trusted section hierarchy and merge child subsections."
        )

    return {
        "mode": mode,
        "explanation": explanation,
        "counts": dict(counts),
        "accepted_density": round(accepted_density, 2),
        "rejection_ratio": round(rejection_ratio, 2),
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.title("Research PDF Structure Analyzer")

st.write(
    "This consolidated test uses PyMuPDF4LLM, confidence scoring, "
    "false-heading rejection, hierarchy detection, subsection merging, "
    "and automatic fallback recommendations."
)

uploaded_file = st.file_uploader(
    "Choose a research PDF",
    type=["pdf"],
)

if uploaded_file is not None:
    try:
        pdf_bytes = uploaded_file.read()

        with st.spinner("Extracting and evaluating document structure..."):
            markdown_text, page_count = extract_markdown_from_pdf(
                pdf_bytes
            )

            raw_candidates = extract_candidates(
                markdown_text,
                page_count,
            )

            evaluated = [
                score_candidate(candidate, page_count)
                for candidate in raw_candidates
            ]

            evaluated = remove_duplicates(evaluated)
            evaluated = attach_parent_titles(evaluated)

            analysis_units = build_analysis_units(evaluated)
            quality = assess_structure_quality(
                evaluated,
                page_count,
            )

        st.success("PDF structure analysis complete.")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Pages", page_count)
        col2.metric("Candidates", len(raw_candidates))
        col3.metric(
            "Analyze sections",
            quality["counts"].get("analyze", 0),
        )
        col4.metric(
            "Rejected",
            quality["counts"].get("reject", 0),
        )

        st.info(
            f"**Recommended processing:** {quality['mode']}  \n"
            f"{quality['explanation']}"
        )

        st.subheader("Decision summary")

        summary_rows = []

        for action in [
            "analyze",
            "merge-with-parent",
            "structure-only",
            "reject",
        ]:
            summary_rows.append(
                {
                    "Action": action,
                    "Count": quality["counts"].get(action, 0),
                }
            )

        st.dataframe(
            summary_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Heading decisions")

        display_rows = []

        for item in evaluated:
            display_rows.append(
                {
                    "Line": item["line_number"],
                    "Heading": item["title"],
                    "Source": item["source"],
                    "Score": item["score"],
                    "Action": item["action"],
                    "Parent": item.get("parent", ""),
                    "Reason": item["reason"],
                }
            )

        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
            height=600,
        )

        st.subheader("Proposed summarization units")

        if analysis_units:
            for index, unit in enumerate(analysis_units, start=1):
                with st.expander(
                    f"{index}. {unit['heading']}",
                    expanded=False,
                ):
                    if unit["children"]:
                        st.write("Merge these subsections into this unit:")

                        for child in unit["children"]:
                            st.write(f"- {child}")
                    else:
                        st.write("No child headings need to be merged.")
        else:
            st.warning(
                "No reliable section units were found. "
                "Use fallback paragraph/page chunking."
            )

        report = {
            "file_name": uploaded_file.name,
            "page_count": page_count,
            "recommended_mode": quality,
            "heading_decisions": evaluated,
            "analysis_units": analysis_units,
        }

        st.download_button(
            "Download structure report (JSON)",
            data=json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
            file_name=(
                Path(uploaded_file.name).stem
                + "_structure_report.json"
            ),
            mime="application/json",
        )

        with st.expander("Markdown preview"):
            st.text_area(
                "First 12,000 characters",
                value=markdown_text[:12000],
                height=500,
            )

    except Exception as error:
        st.error(f"Unable to process the PDF: {error}")
