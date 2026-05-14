#!/usr/bin/env python3
"""Extract URLs from a PDF, scrape page text, deduplicate, and save to TXT."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Iterable, List

import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

URL_PATTERN = re.compile(r"https?://[^\s<>\]\)\}\"']+")


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    text_chunks: List[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_chunks.append(page_text)
    return "\n".join(text_chunks)


def find_urls(text: str) -> List[str]:
    raw_urls = URL_PATTERN.findall(text)
    cleaned: List[str] = []
    for url in raw_urls:
        cleaned_url = url.rstrip(".,;:!?)\"]}")
        cleaned.append(cleaned_url)
    return cleaned


def unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def scrape_text(url: str, timeout: float) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        element.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def build_output(urls: List[str], timeout: float) -> str:
    output_parts: List[str] = []
    content_hashes = set()
    for url in urls:
        try:
            content = scrape_text(url, timeout)
        except Exception as exc:  # noqa: BLE001 - surface the error in output
            content = f"[ERROR] {exc}"

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest in content_hashes:
            continue
        content_hashes.add(digest)

        output_parts.append(f"URL: {url}\n{content}\n")
    return "\n".join(output_parts).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract URLs from a PDF, scrape web pages, deduplicate, and save to TXT."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument("output", type=Path, help="Path to the output TXT file")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout (seconds)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.pdf.exists():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    text = extract_text_from_pdf(args.pdf)
    urls = unique_preserve_order(find_urls(text))
    if not urls:
        print("No URLs found in PDF.", file=sys.stderr)
        return 1

    output_text = build_output(urls, args.timeout)
    args.output.write_text(output_text, encoding="utf-8")

    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
