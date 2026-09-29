"""Add an approved PDF or text file to the canonical RAG library and vector index."""

import argparse
import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.rag import KnowledgeChunk, KnowledgeDocument
from app.services.rag import close_rag_service, get_rag_service


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_pages(path: Path) -> list[tuple[int | None, str]]:
    if path.suffix.lower() != ".pdf":
        return [(None, path.read_text(encoding="utf-8"))]
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit("Install the rag-authoring dependency to ingest PDFs.") from exc
    with fitz.open(path) as document:
        return [(number, page.get_text("text")) for number, page in enumerate(document, 1)]


def chunk_pages(
    pages: list[tuple[int | None, str]], *, words_per_chunk: int = 220, overlap: int = 35
) -> list[tuple[int | None, str]]:
    chunks: list[tuple[int | None, str]] = []
    step = words_per_chunk - overlap
    for page_number, raw_text in pages:
        words = raw_text.split()
        for start in range(0, len(words), step):
            content = " ".join(words[start : start + words_per_chunk]).strip()
            if len(content) >= 80:
                chunks.append((page_number, content))
            if start + words_per_chunk >= len(words):
                break
    return chunks


async def ingest(args: argparse.Namespace) -> None:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".pdf", ".txt", ".md"}:
        raise SystemExit("Provide an existing .pdf, .txt, or .md file.")
    pages = read_pages(path)
    chunks = chunk_pages(pages)
    if not chunks:
        raise SystemExit("No readable text was found in the source.")
    document_checksum = digest("\n".join(text for _page, text in pages))

    async with SessionLocal() as db:
        existing = (
            await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.checksum == document_checksum
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise SystemExit(f"This source is already stored as '{existing.title}'.")
        document = KnowledgeDocument(
            title=args.title,
            publisher=args.publisher,
            source_url=args.source_url,
            source_type=args.source_type,
            subject=args.subject,
            edition=args.edition,
            checksum=document_checksum,
        )
        db.add(document)
        await db.flush()
        for index, (page_number, content) in enumerate(chunks):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    chapter=args.chapter or path.stem,
                    page_start=page_number,
                    page_end=page_number,
                    content=content,
                    checksum=digest(f"{document.id}:{index}:{content}"),
                )
            )
        await db.commit()
        try:
            indexed = await get_rag_service().sync_knowledge(db)
            print(f"Stored '{document.title}' with {len(chunks)} chunks; indexed {indexed}.")
        finally:
            close_rag_service()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--title", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument(
        "--subject",
        required=True,
        choices=["general-knowledge", "elementary-mathematics", "english"],
    )
    parser.add_argument("--source-url")
    parser.add_argument("--source-type", default="approved_upload")
    parser.add_argument("--edition")
    parser.add_argument("--chapter")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(ingest(parse_args()))
