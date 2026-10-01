"""Build a public CDS PDF catalogue from UPSC's current and archived listings.

No invented questions, dates or answer keys. Verify the PDF signature with a
small streamed request; do not download hundreds of megabytes into the repo.
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

SOURCES = (
    "https://www.upsc.gov.in/examinations/previous-question-papers",
    "https://www.upsc.gov.in/examinations/previous-question-papers/archives",
)
SUBJECTS = {
    "english": "English",
    "general-knowledge": "General Knowledge",
    "elementary-mathematics": "Elementary Mathematics",
}


def official_pdf(url):
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"upsc.gov.in", "www.upsc.gov.in"}
        and parsed.path.lower().endswith(".pdf")
        and not parsed.username
    )


class ArchiveParser(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.papers = []
        self.depth = 0
        self.in_caption = False
        self.in_item = False
        self.caption = ""
        self.item = ""
        self.hrefs = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.caption, self.items = "", []
        if self.depth != 1:
            return
        if tag == "caption":
            self.in_caption = True
        if tag == "li":
            self.in_item, self.item, self.hrefs = True, "", []
        if tag == "a" and self.in_item:
            href = dict(attrs).get("href", "")
            self.hrefs.append(urljoin(self.source, href))

    def handle_data(self, data):
        if self.in_caption:
            self.caption += data
        if self.in_item:
            self.item += data

    def handle_endtag(self, tag):
        if tag == "caption":
            self.in_caption = False
        if tag == "li" and self.in_item:
            self.items.append((" ".join(self.item.split()), self.hrefs))
            self.in_item = False
        if tag == "table":
            if self.depth == 1:
                self.finish_table()
            self.depth -= 1

    def finish_table(self):
        match = re.fullmatch(
            r"Combined Defence Services Examination\s*\((I|II)\),?\s*(\d{4})",
            " ".join(self.caption.split()),
            re.I,
        )
        if not match:
            return
        found = set()
        for label, hrefs in self.items:
            for slug, title in SUBJECTS.items():
                subject_label = label.split("(", 1)[0].strip().casefold()
                if subject_label not in {
                    title.casefold(),
                    "general english" if slug == "english" else title.casefold(),
                }:
                    continue
                urls = [url for url in hrefs if official_pdf(url)]
                if len(urls) != 1 or slug in found:
                    raise ValueError("Ambiguous official PDF listing: " + self.caption)
                found.add(slug)
                self.papers.append(
                    {
                        "year": int(match[2]),
                        "cycle": match[1].upper(),
                        "subject_slug": slug,
                        "source_url": urls[0],
                        "listing_url": self.source,
                    }
                )
        if found != set(SUBJECTS):
            raise ValueError("Incomplete official subject listing: " + self.caption)


def verify_pdf(paper):
    for attempt in range(2):
        try:
            with requests.get(
                paper["source_url"], stream=True, timeout=(15, 30), headers={"Range": "bytes=0-7"}
            ) as response:
                response.raise_for_status()
                if not official_pdf(response.url) or not response.raw.read(8).startswith(b"%PDF-"):
                    raise ValueError("Source is not an official PDF")
                return {**paper, "pdf_checked": True}
        except (requests.RequestException, ValueError):
            if attempt:
                raise ValueError(
                    f"PDF check failed: {paper['year']} {paper['cycle']} {paper['subject_slug']}"
                ) from None


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--output", type=Path, required=True)
    options = args.parse_args()
    records = {}
    for source in SOURCES:
        response = requests.get(source, timeout=(15, 45))
        response.raise_for_status()
        parser = ArchiveParser(source)
        parser.feed(response.text)
        if not parser.papers:
            raise ValueError("UPSC listing structure changed; no papers discovered")
        for paper in parser.papers:
            key = paper["year"], paper["cycle"], paper["subject_slug"]
            if key in records and records[key]["source_url"] != paper["source_url"]:
                raise ValueError("Conflicting official PDF listing")
            records[key] = paper
    with ThreadPoolExecutor(max_workers=3) as pool:
        papers = list(pool.map(verify_pdf, records.values()))
    papers.sort(key=lambda p: (-p["year"], p["cycle"], p["subject_slug"]))
    bundle = {
        "version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "sources": list(SOURCES),
        "papers": papers,
        "coverage_note": "All CDS PDFs listed in UPSC's current and archived question-paper "
        "pages at the time of checking. The earliest listing is CDS II 2016. "
        "CDS I 2016 and earlier papers are not listed there; this is not an all-time archive.",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verified_papers": len(papers),
                "years": sorted({p["year"] for p in papers}, reverse=True),
            }
        )
    )


if __name__ == "__main__":
    main()
