"""
Generate a tailored resume by modifying the original .docx directly.
Preserves all formatting (fonts, spacing, margins, borders).
Returns .docx bytes.
"""
from pathlib import Path
import io

DOCX_PATH = Path(__file__).parent.parent / "profile" / "resume.docx"


def _replace_in_paragraph(para, original: str, rewritten: str) -> bool:
    """
    Replace `original` text with `rewritten` in a paragraph's runs,
    preserving all run formatting. Returns True if a replacement was made.
    """
    full_text = para.text
    if original not in full_text:
        return False

    # Best case: text is entirely within one run
    for run in para.runs:
        if original in run.text:
            run.text = run.text.replace(original, rewritten, 1)
            return True

    # Text spans multiple runs — consolidate into the first run, drop the rest
    new_text = full_text.replace(original, rewritten, 1)
    if para.runs:
        para.runs[0].text = new_text
        for run in para.runs[1:]:
            run.text = ""
    return True


def apply_changes(approved_changes: list[dict], company: str = "") -> tuple[bytes, str]:
    """
    Open the original docx, apply approved text substitutions.
    Returns (docx_bytes, filename).
    """
    from docx import Document

    if not DOCX_PATH.exists():
        raise FileNotFoundError(f"Base resume not found at {DOCX_PATH}")

    doc = Document(str(DOCX_PATH))

    for change in approved_changes:
        original = change.get("original", "").strip()
        rewritten = change.get("rewritten", "").strip()
        if not original or not rewritten:
            continue

        for para in doc.paragraphs:
            if _replace_in_paragraph(para, original, rewritten):
                break  # each change applies once

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    filename = f"Rachita Kumar Resume - {company}.docx" if company else "Rachita Kumar Resume - Tailored.docx"
    return buf.read(), filename
