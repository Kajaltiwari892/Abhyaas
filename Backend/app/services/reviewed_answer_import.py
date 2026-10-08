"""Trusted editorial imports, bound to the exact paper and question text.

This is an offline maintainer operation, never an endpoint taking student keys.
Validate the entire manifest before committing; reruns are idempotent and final
official keys win. Changes to choices, context or source invalidate old reviews.
"""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.papers import PaperAttempt, PreviousPaper
from app.models.practice import Subject
from app.services.paper_answers import (
    question_content_fingerprint,
    question_fingerprint,
    refresh_attempt_grade,
    save_review,
    stored_answer,
)


async def import_reviews(db: AsyncSession, payload: dict, *, apply: bool) -> dict:
    if (
        payload.get("version") != 1
        or payload.get("series") != "A"
        or payload.get("cycle") not in {"I", "II"}
    ):
        raise ValueError("Use a version 1 manifest for the exact Series A paper")
    paper = await db.scalar(
        select(PreviousPaper)
        .join(Subject)
        .options(
            selectinload(PreviousPaper.questions),
            selectinload(PreviousPaper.subject),
        )
        .where(
            PreviousPaper.year == payload["year"],
            PreviousPaper.cycle == payload["cycle"],
            Subject.slug == payload["subject_slug"],
        )
    )
    if (
        not paper
        or not paper.source_checksum
        or paper.source_checksum != payload.get("source_checksum")
    ):
        raise ValueError("The paper source does not match this reviewed manifest")
    items = payload.get("questions")
    if not isinstance(items, list) or not 1 <= len(items) <= paper.official_question_count:
        raise ValueError("Supply checked answers for questions in this paper")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    rows = {q.number: q for q in paper.questions}
    counts = {"saved": 0, "ready": 0, "existing": 0, "official_preserved": 0}
    seen = set()
    for item in items:
        number = item.get("number")
        if type(number) is not int or number in seen or number not in rows:
            raise ValueError("Each question number must belong to the paper and occur once")
        seen.add(number)
        q = rows[number]
        if q.is_verified:
            counts["official_preserved"] += 1
            continue
        if (
            stored_answer(q, paper)
            and (q.answer_review or {}).get("evidence", {}).get("manifest_digest") == digest
        ):
            counts["existing"] += 1
            continue
        if not (
            item.get("content_fingerprint") == question_content_fingerprint(q)
            or item.get("fingerprint") == question_fingerprint(q)
        ):
            raise ValueError(f"Q{number}: its text or options have changed since this review")
        # save_review validates even in dry-run; roll back all staged changes later.
        save_review(
            q,
            item.get("correct_index"),
            item.get("explanation", ""),
            method="editorial",
            evidence={
                "manifest_digest": digest,
                "paper_source": paper.source_url,
                "source_checksum": paper.source_checksum,
                "series": "A",
            },
        )
        counts["ready"] += 1
    if apply:
        attempts = (
            await db.scalars(
                select(PaperAttempt)
                .options(selectinload(PaperAttempt.answers))
                .where(
                    PaperAttempt.paper_id == paper.id,
                    PaperAttempt.status == "completed",
                )
            )
        ).all()
        for attempt in attempts:
            refresh_attempt_grade(attempt, paper, list(paper.questions), list(attempt.answers))
        await db.commit()
        counts["saved"] = counts["ready"]
    else:
        await db.rollback()
    return counts
