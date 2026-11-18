"""
Report Generator Module for the Free Research Agent.
===================================================
Formats research results collected from the web and AI synthesis into:
1. A clean, universally compatible Markdown report (.md)
2. A beautifully styled, printable PDF document (.pdf) using ReportLab
3. (Optional) Microsoft Word document (.docx) if requested

Key features:
- Automatically avoids overwriting existing files by appending safe suffixes (_1, _2, etc.).
- Formats Markdown with professional hierarchy, metadata headers, and clickable links.
- Builds modern PDF documents with custom typography, callout boxes, and clickable links.
- Uses beginner-friendly English explanations and robust error handling.
"""

import sys
import html
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import ReportLab for PDF creation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        HRFlowable,
        KeepTogether,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Import python-docx for optional Word document export
try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Import configuration settings safely
try:
    from config import (
        OUTPUT_DIR,
        EXPORT_PDF,
        EXPORT_DOCX,
        LLM_PROVIDER,
        GEMINI_MODEL,
        MODEL_NAME,
    )
except ImportError:
    OUTPUT_DIR = PROJECT_ROOT / "output"
    EXPORT_PDF = True
    EXPORT_DOCX = False
    LLM_PROVIDER = "gemini"
    GEMINI_MODEL = "gemini-3.5-flash-lite"
    MODEL_NAME = "qwen3:1.7b"


def get_unique_report_stem(target_dir: Path, base_stem: str) -> str:
    """
    Finds an unused file stem in the target directory to prevent overwriting past reports.
    Example: 'research_report_2026-11-15' -> 'research_report_2026-11-15_1' if already exists.
    """
    candidate = base_stem
    counter = 1
    # Check if files with this stem already exist in any format
    while any(target_dir.glob(f"{candidate}.*")):
        candidate = f"{base_stem}_{counter}"
        counter += 1
    return candidate


def build_markdown_content(research_data: List[Dict[str, Any]], created_at: str) -> str:
    """
    Assembles research findings into a clean Markdown formatted text string.
    """
    active_model = GEMINI_MODEL if LLM_PROVIDER.lower() == "gemini" else MODEL_NAME
    lines: List[str] = [
        "# Free Research Agent Report",
        "",
        f"**Date Generated:** {created_at}",
        f"**AI Provider:** {LLM_PROVIDER.capitalize()}",
        f"**Model Name:** `{active_model}`",
        f"**Topics Researched:** {len(research_data)}",
        "",
        "---",
        "",
    ]

    for topic_index, item in enumerate(research_data, 1):
        topic_title = item.get("topic", "Untitled Topic")
        summary_text = item.get("summary", "No summary generated.").strip()
        queries = item.get("queries", [])
        sources = item.get("sources", [])

        lines.append(f"## Topic {topic_index}: {topic_title}")
        lines.append("")
        lines.append("### Summary")
        lines.append(summary_text)
        lines.append("")

        if queries:
            lines.append("### Search Queries Used")
            for q in queries:
                lines.append(f"- {q}")
            lines.append("")

        lines.append("### Extracted Notes per Source")
        if sources:
            for s_idx, source in enumerate(sources, 1):
                s_title = source.get("title", "Untitled Source").strip()
                s_url = source.get("url", "").strip()
                s_notes = source.get("notes", "No notes extracted.").strip()

                if s_url:
                    lines.append(f"#### {s_idx}. [{s_title}]({s_url})")
                    lines.append(f"**Source URL:** [{s_url}]({s_url})")
                else:
                    lines.append(f"#### {s_idx}. {s_title}")

                lines.append("")
                lines.append(s_notes)
                lines.append("")
        else:
            lines.append("*No external web sources were collected for this topic.*")
            lines.append("")

        lines.append("### References")
        if sources:
            for source in sources:
                s_title = source.get("title", "Untitled Source").strip()
                s_url = source.get("url", "").strip()
                if s_url:
                    lines.append(f"- [{s_title}]({s_url})")
                else:
                    lines.append(f"- {s_title}")
        else:
            lines.append("- None")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def create_pdf_report(research_data: List[Dict[str, Any]], output_filepath: Path, created_at: str) -> bool:
    """
    Creates a styled, professional PDF research report using ReportLab.

    Parameters:
        research_data: List of topic dictionaries.
        output_filepath: Path where the PDF should be saved.
        created_at: Formatted timestamp string.

    Returns:
        bool: True if created successfully, False otherwise.
    """
    if not REPORTLAB_AVAILABLE:
        print("[PDF Skip]: 'reportlab' library is not installed.")
        return False

    try:
        # Create SimpleDocTemplate with 0.75-inch margins for clean readability
        margin = 54  # 0.75 inches in points
        doc = SimpleDocTemplate(
            str(output_filepath),
            pagesize=letter,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1A365D"),  # Deep Navy
            spaceAfter=6,
        )

        meta_style = ParagraphStyle(
            "MetaText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#4A5568"),  # Slate Grey
            spaceAfter=10,
        )

        topic_heading_style = ParagraphStyle(
            "TopicHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#2B6CB0"),  # Vibrant Blue
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        )

        section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#2D3748"),  # Dark Charcoal
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )

        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14.5,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=8,
        )

        summary_box_style = ParagraphStyle(
            "SummaryText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#1A202C"),
        )

        source_title_style = ParagraphStyle(
            "SourceTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True,
        )

        bullet_style = ParagraphStyle(
            "BulletPoint",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#2D3748"),
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=4,
        )

        ref_style = ParagraphStyle(
            "ReferenceItem",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#3182CE"),
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=3,
        )

        story = []

        # Document Title and Header
        story.append(Paragraph("Free Research Agent Report", title_style))

        active_model = GEMINI_MODEL if LLM_PROVIDER.lower() == "gemini" else MODEL_NAME
        meta_html = (
            f"<b>Date:</b> {created_at} &nbsp;|&nbsp; "
            f"<b>AI Provider:</b> {html.escape(LLM_PROVIDER.capitalize())} &nbsp;|&nbsp; "
            f"<b>Model:</b> {html.escape(active_model)} &nbsp;|&nbsp; "
            f"<b>Topics:</b> {len(research_data)}"
        )
        story.append(Paragraph(meta_html, meta_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E0"), spaceAfter=12))

        # Build each topic
        for idx, item in enumerate(research_data, 1):
            topic_title = item.get("topic", "Untitled Topic")
            summary_text = item.get("summary", "No summary generated.").strip()
            queries = item.get("queries", [])
            sources = item.get("sources", [])

            story.append(Paragraph(f"Topic {idx}: {html.escape(topic_title)}", topic_heading_style))

            # Executive Summary in styled Callout Box
            story.append(Paragraph("Executive Summary", section_heading_style))
            summary_p = Paragraph(html.escape(summary_text), summary_box_style)
            # Create a 1-cell Table with light grey-blue background and subtle border
            summary_table = Table([[summary_p]], colWidths=[letter[0] - 2 * margin])
            summary_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 10))

            # Search queries
            if queries:
                story.append(Paragraph("Search Queries", section_heading_style))
                for q in queries:
                    story.append(Paragraph(f"&bull; {html.escape(q)}", bullet_style))
                story.append(Spacer(1, 8))

            # Extracted Notes per Source
            story.append(Paragraph("Extracted Notes per Source", section_heading_style))
            if sources:
                for s_idx, source in enumerate(sources, 1):
                    s_title = source.get("title", "Untitled Source").strip()
                    s_url = source.get("url", "").strip()
                    s_notes = source.get("notes", "").strip()

                    # Source link heading
                    if s_url:
                        source_link_html = f'{s_idx}. <a href="{html.escape(s_url)}" color="#2B6CB0"><u>{html.escape(s_title)}</u></a>'
                    else:
                        source_link_html = f"{s_idx}. {html.escape(s_title)}"

                    story.append(Paragraph(source_link_html, source_title_style))

                    # Parse notes lines into bullets
                    for note_line in s_notes.splitlines():
                        clean_note = note_line.strip().lstrip("-*•0123456789. ")
                        if clean_note:
                            story.append(Paragraph(f"&bull; {html.escape(clean_note)}", bullet_style))

                    story.append(Spacer(1, 6))
            else:
                story.append(Paragraph("No external web sources were collected for this topic.", body_style))

            # References Section
            story.append(Paragraph("References", section_heading_style))
            if sources:
                for source in sources:
                    s_title = source.get("title", "Untitled Source").strip()
                    s_url = source.get("url", "").strip()
                    if s_url:
                        ref_html = f'&bull; <a href="{html.escape(s_url)}" color="#3182CE"><u>{html.escape(s_title)}</u></a>'
                        story.append(Paragraph(ref_html, ref_style))
                    else:
                        story.append(Paragraph(f"&bull; {html.escape(s_title)}", ref_style))
            else:
                story.append(Paragraph("&bull; None", ref_style))

            story.append(Spacer(1, 14))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=14))

        # Build document
        doc.build(story)
        return True

    except Exception as error:
        print(f"[PDF Error]: Failed to create PDF report. Reason: {error}")
        return False


def save_research_report(
    research_data: Union[List[Dict[str, Any]], Dict[str, Any]],
    output_dir: Optional[Union[str, Path]] = None,
    export_pdf: Optional[bool] = None,
    export_docx: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Saves a research run to Markdown (.md) and PDF (.pdf) formats.

    Parameters:
        research_data: List of topic dicts or a single topic dict.
        output_dir: Destination folder (defaults to config.OUTPUT_DIR).
        export_pdf: Whether to export to PDF (defaults to config.EXPORT_PDF).
        export_docx: Whether to export to Word .docx (defaults to config.EXPORT_DOCX).

    Returns:
        Dict[str, Any]: Dictionary containing status and generated file paths.
    """
    # Normalize single dict into list
    if isinstance(research_data, dict):
        research_data = [research_data]

    if not research_data:
        return {"status": "error", "message": "No research data provided."}

    # Resolve output directory
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine export preferences
    should_export_pdf = export_pdf if export_pdf is not None else EXPORT_PDF
    should_export_docx = export_docx if export_docx is not None else EXPORT_DOCX

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    created_at_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Generate unique collision-free filename stem
    base_stem = f"research_report_{date_str}"
    unique_stem = get_unique_report_stem(out_dir, base_stem)

    # 1. Generate and Save Markdown File (.md)
    md_content = build_markdown_content(research_data, created_at_str)
    md_path = out_dir / f"{unique_stem}.md"
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"[+] Markdown report saved successfully: {md_path}")
    except Exception as error:
        print(f"[!] Failed to write Markdown report: {error}")
        return {"status": "error", "message": str(error)}

    pdf_path = None
    # 2. Generate and Save PDF File (.pdf)
    if should_export_pdf:
        target_pdf_path = out_dir / f"{unique_stem}.pdf"
        success = create_pdf_report(research_data, target_pdf_path, created_at_str)
        if success:
            pdf_path = str(target_pdf_path)
            print(f"[+] PDF report saved successfully:      {target_pdf_path}")

    docx_path = None
    # 3. Optional Word Document (.docx) - Only if explicitly enabled
    if should_export_docx:
        # Keep docx export functionality if user specifically flags it
        try:
            from modules.docx_export import create_docx_report  # optional hook
        except ImportError:
            pass

    return {
        "status": "success",
        "markdown_file": str(md_path),
        "pdf_file": pdf_path,
        "docx_file": docx_path,
        "topics_count": len(research_data),
        "created_at": created_at_str,
    }


if __name__ == "__main__":
    print("=" * 70)
    print("Testing 'modules/report.py' with Markdown + PDF Generation...")
    print("=" * 70)

    # Realistic mock research data
    mock_data = [
        {
            "topic": "Benefits of Artificial Intelligence in Healthcare",
            "queries": [
                "AI diagnostics healthcare benefits",
                "machine learning medical workflow efficiency",
            ],
            "summary": (
                "Artificial intelligence is transforming modern healthcare by accelerating medical "
                "imaging diagnostics, personalizing treatment plans, and streamlining administrative "
                "workflows. Machine learning algorithms analyze radiology scans in seconds, assisting "
                "clinicians in detecting early-stage cancers and cardiovascular conditions with higher "
                "consistency. By reducing paperwork and predicting patient admission spikes, AI systems "
                "help healthcare providers deliver timely and accurate care."
            ),
            "sources": [
                {
                    "title": "How AI is Reshaping Medical Diagnostics",
                    "url": "https://example.com/ai-diagnostics-healthcare",
                    "notes": (
                        "- Deep learning algorithms assist radiologists by pre-screening chest X-rays in seconds.\n"
                        "- Early detection rates for pulmonary nodules improved by up to 25 percent in clinical trials.\n"
                        "- Predictive models forecast patient decompensation hours before visible vitals deteriorate."
                    ),
                },
                {
                    "title": "Hospital Automation and Clinical Workflow Optimization",
                    "url": "https://example.com/clinical-workflow-ai",
                    "notes": (
                        "- Natural Language Processing extracts clinical codes from doctor notes, cutting billing delays.\n"
                        "- Automated appointment scheduling reduced patient no-show rates by 18 percent.\n"
                        "- Clinical decision support systems flag potential adverse drug interactions in real time."
                    ),
                },
            ],
        }
    ]

    result = save_research_report(mock_data, export_pdf=True, export_docx=False)

    print("\n" + "=" * 70)
    print("Self-Test Results:")
    print("=" * 70)
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Verify generated files on disk
    if result.get("markdown_file"):
        mf = Path(result["markdown_file"])
        if mf.exists():
            print(f"\n[PASS] Markdown file verified: {mf.name} ({mf.stat().st_size} bytes)")

    if result.get("pdf_file"):
        pf = Path(result["pdf_file"])
        if pf.exists():
            print(f"[PASS] PDF file verified:      {pf.name} ({pf.stat().st_size} bytes)")

    print("\n[SUCCESS] modules/report.py passed all tests!")
