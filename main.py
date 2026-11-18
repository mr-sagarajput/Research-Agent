"""
Main pipeline entry point for the Free Research Agent.
Orchestrates the entire research flow:
1. Generates search queries using LLM.
2. Performs web search using DuckDuckGo.
3. Fetches and cleans web pages one by one.
4. Extracts 3-5 key points per page using LLM.
5. Synthesizes an approximately 200-word topic summary strictly from notes.
6. Saves dated Markdown (and optional .docx) research reports.
7. Supports self-test mode and multi-topic execution.
"""

import sys
import argparse
from typing import List, Dict, Any

from config import (
    QUERIES_PER_TOPIC,
    RESULTS_PER_QUERY,
    PAGE_LIMIT,
    LLM_PROVIDER,
    GEMINI_MODEL,
    MODEL_NAME,
    EXPORT_PDF,
    EXPORT_DOCX,
)
from modules.llm import query_llm
from modules.search import search_web, generate_search_queries, deduplicate_search_results
from modules.fetch import fetch_article_text
from modules.report import save_research_report


def extract_notes_from_page(page_title: str, url: str, article_text: str) -> str:
    """
    Prompts the LLM to extract 3 to 5 key points from an individual web page.
    Uses only that page's text to prevent hallucinations.

    Parameters:
        page_title (str): Title of the page.
        url (str): Source link.
        article_text (str): Cleaned article body text (truncated to budget).

    Returns:
        str: Bullet points extracted by the model.
    """
    system_prompt = (
        "You are an objective research assistant. "
        "Extract 3 to 5 key factual points from the text provided. "
        "Use ONLY facts stated in the text. Format each point as a bullet starting with '- '."
    )
    user_prompt = (
        f"Source: {page_title} ({url})\n\n"
        f"Article Text:\n{article_text}\n\n"
        "Extract 3 to 5 concise, factual key points in clear English:"
    )

    return query_llm(user_prompt, system_prompt=system_prompt)


def generate_topic_summary(topic: str, sources_data: List[Dict[str, Any]]) -> str:
    """
    Synthesizes an approximately 200-word summary of the topic
    using ONLY the collected per-source notes.

    Parameters:
        topic (str): The research subject.
        sources_data (List[Dict[str, Any]]): Collected notes and URLs.

    Returns:
        str: Comprehensive research summary.
    """
    if not sources_data:
        return "No valid sources could be retrieved to summarize this topic."

    # Compile all extracted notes into a structured text block
    compiled_notes = []
    for idx, item in enumerate(sources_data, 1):
        compiled_notes.append(f"Source {idx} ({item['title']}):\n{item['notes']}")

    notes_block = "\n\n".join(compiled_notes)

    system_prompt = (
        "You are an expert research analyst. "
        "Write an informative, well-structured research summary in clear English. "
        "Target length: approximately 200 words. "
        "Rely strictly on the provided research notes. Do not invent outside information."
    )
    user_prompt = (
        f"Topic: {topic}\n\n"
        f"Collected Research Notes:\n{notes_block}\n\n"
        "Write an approximately 200-word summary synthesizing these findings:"
    )

    return query_llm(user_prompt, system_prompt=system_prompt)


def research_topic(topic: str, max_pages: int = PAGE_LIMIT) -> Dict[str, Any]:
    """
    Executes the complete research pipeline for a single topic.

    Parameters:
        topic (str): The topic to investigate.
        max_pages (int): Maximum web pages to open (1 in test mode, default 4).

    Returns:
        Dict[str, Any]: Full topic research results (topic, queries, sources, summary).
    """
    print("\n" + "=" * 70)
    print(f"[*] Starting Research on Topic: '{topic}'")
    print(f"[*] Page Limit: {max_pages} | Active Provider: {LLM_PROVIDER}")
    print("=" * 70)

    # Step 1: Generate search queries
    print("\n[Step 1/4] Generating search queries with AI...")
    queries = generate_search_queries(topic, num_queries=QUERIES_PER_TOPIC)
    print(f"Generated {len(queries)} queries:")
    for q in queries:
        print(f"  - '{q}'")

    # Step 2: Search web and collect candidate URLs
    print("\n[Step 2/4] Searching web via DuckDuckGo...")
    raw_candidates = []
    for q in queries:
        results = search_web(q, max_results=RESULTS_PER_QUERY)
        raw_candidates.extend(results)

    candidate_urls = deduplicate_search_results(raw_candidates)

    print(f"Found {len(candidate_urls)} candidate articles.")

    # Step 3: Fetch pages and extract notes one by one
    print(f"\n[Step 3/4] Processing up to {max_pages} pages (one at a time to protect RAM)...")
    sources_data = []

    for item in candidate_urls:
        if len(sources_data) >= max_pages:
            break

        url = item["url"]
        title = item["title"]
        print(f"\n-> Fetching: {title}")
        print(f"   URL: {url}")

        article_text = fetch_article_text(url)
        if not article_text:
            # Skip reason is already logged by fetch_article_text
            continue

        print(f"   [Extracted {len(article_text)} chars]. Calling AI for key points...")
        notes = extract_notes_from_page(title, url, article_text)

        if notes:
            sources_data.append({
                "title": title,
                "url": url,
                "notes": notes,
            })
            print("   [Key points extracted successfully]")

    # Step 4: Synthesize final ~200-word topic summary
    print("\n[Step 4/4] Generating final topic summary from notes...")
    summary = generate_topic_summary(topic, sources_data)

    print("\n" + "=" * 70)
    print(f"[Research Complete for '{topic}']")
    print("=" * 70)
    print(f"\nSummary:\n{summary}\n")
    print(f"Processed {len(sources_data)} source(s):")
    for idx, s in enumerate(sources_data, 1):
        print(f"\n--- Source {idx}: {s['title']} ---")
        print(f"URL: {s['url']}")
        print(f"Key Points:\n{s['notes']}")

    return {
        "topic": topic,
        "queries": queries,
        "sources": sources_data,
        "summary": summary,
    }


def run_pipeline(
    topics: List[str],
    max_pages: int = PAGE_LIMIT,
    export_pdf: bool = None,
    export_docx: bool = None,
) -> Dict[str, Any]:
    """
    Runs research across one or more topics and saves a unified, dated report
    in Markdown (.md) and PDF (.pdf) formats.

    Parameters:
        topics (List[str]): List of research topics.
        max_pages (int): Page limit per topic.
        export_pdf (bool): Whether to export to .pdf (defaults to config.EXPORT_PDF).
        export_docx (bool): Whether to export to .docx (defaults to config.EXPORT_DOCX).

    Returns:
        Dict[str, Any]: Report file paths and summary metadata.
    """
    clean_topics = [t.strip() for t in topics if t.strip()]
    if not clean_topics:
        print("[Error]: No valid topics provided.")
        return {}

    all_results = []
    for topic in clean_topics:
        result = research_topic(topic, max_pages=max_pages)
        all_results.append(result)

    # Save consolidated research report (Markdown + PDF)
    print("\n" + "=" * 70)
    print("[*] Saving Consolidated Research Report...")
    print("=" * 70)
    report_info = save_research_report(
        all_results,
        export_pdf=export_pdf,
        export_docx=export_docx,
    )

    print(f"\n[+] Markdown Report: {report_info.get('markdown_file')}")
    if report_info.get("pdf_file"):
        print(f"[+] PDF Document:    {report_info.get('pdf_file')}")
    if report_info.get("docx_file"):
        print(f"[+] Word Document:   {report_info.get('docx_file')}")

    return report_info


def main():
    parser = argparse.ArgumentParser(description="Free Local/Cloud Research Agent")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-test mode (limited to 1 topic and 1 page)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Specify a single research topic from the command line",
    )
    parser.add_argument(
        "--topics",
        nargs="+",
        default=None,
        help="Specify multiple research topics separated by spaces (e.g. --topics 'Topic 1' 'Topic 2')",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Disable PDF export (generates Markdown only)",
    )
    parser.add_argument(
        "--docx",
        action="store_true",
        help="Enable optional Microsoft Word (.docx) export",
    )
    args = parser.parse_args()

    # Determine export preferences (Default: Markdown + PDF)
    export_pdf = False if args.no_pdf else EXPORT_PDF
    export_docx = True if args.docx else EXPORT_DOCX

    if args.test:
        print("[*] Running in SELF-TEST MODE (capped at 1 page)...")
        test_topic = "Free local LLMs vs cloud APIs"
        run_pipeline([test_topic], max_pages=1, export_pdf=export_pdf, export_docx=export_docx)
    elif args.topics:
        run_pipeline(args.topics, max_pages=PAGE_LIMIT, export_pdf=export_pdf, export_docx=export_docx)
    elif args.topic:
        run_pipeline([args.topic], max_pages=PAGE_LIMIT, export_pdf=export_pdf, export_docx=export_docx)
    else:
        user_input = input("Enter research topic(s), separated by commas: ").strip()
        if user_input:
            topics = [t.strip() for t in user_input.split(",") if t.strip()]
            run_pipeline(topics, max_pages=PAGE_LIMIT, export_pdf=export_pdf, export_docx=export_docx)
        else:
            print("No topic entered. Exiting.")


if __name__ == "__main__":
    main()
