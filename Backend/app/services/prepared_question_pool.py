"""Use checked lesson questions before asking a provider to create more.

Public originals are published ahead of time. A student's independently checked
questions remain private. An exact lesson tag is mandatory for either kind;
legacy, untagged generated grammar questions must never leak into a new chapter.
"""

import re
from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.practice import PracticeAnswer, PracticeAttempt, Question, Topic
from app.services.daily_quiz import matches_lesson
from app.services.study_curriculum import find_unit


def fingerprint(prompt: str) -> str:
    return re.sub(r"\W+", "", prompt).casefold()


async def choose_prepared_questions(
    db: AsyncSession,
    user_id: str,
    task,
    *,
    exclude_ids: Iterable[str] = (),
    exclude_prompts: Iterable[str] = (),
    limit: int = 50,
) -> list[Question]:
    unit = find_unit(task.curriculum_key)
    if unit is None or limit <= 0:
        return []
    topics = [task.topic_slug]
    if task.subject_slug == "english" and task.topic_slug in {"grammar", "error-spotting"}:
        topics = ["grammar", "error-spotting"]
    answered = (
        select(PracticeAnswer.id)
        .join(PracticeAttempt)
        .where(PracticeAnswer.question_id == Question.id, PracticeAttempt.user_id == user_id)
        .exists()
    )
    rows = await db.execute(
        select(Question, answered.label("seen_before"))
        .join(Topic)
        .where(
            Topic.subject.has(slug=task.subject_slug),
            Topic.slug.in_(topics),
            Question.is_active.is_(True),
            or_(Question.owner_user_id.is_(None), Question.owner_user_id == user_id),
            ~Question.id.in_(list(exclude_ids)),
        )
        .order_by(answered, Question.id)
    )
    eligible = []
    for question, seen_before in rows:
        source = question.provenance or {}
        if (
            len(question.options) != 4
            or type(question.correct_index) is not int
            or not 0 <= question.correct_index < 4
        ):
            continue
        kind = source.get("kind")
        if kind == "pyq":
            approved = (
                question.owner_user_id is None
                and source.get("paper_question_id")
                and source.get("source_url")
                and matches_lesson(question, unit)
            )
        else:
            tagged_unit = find_unit(source.get("curriculum_key"))
            approved = bool(question.explanation.strip()) and tagged_unit == unit and (
                (
                    kind == "curated"
                    and question.owner_user_id is None
                    and source.get("review_status") == "content_checked"
                )
                or (
                    kind == "generated"
                    and question.owner_user_id == user_id
                    and source.get("review_status") == "independent_ai_checked"
                )
            )
        if approved:
            # New questions first; within each group prefer genuine PYQs.
            eligible.append((bool(seen_before), kind != "pyq", question))
    eligible.sort(key=lambda item: (item[0], item[1], item[2].id))
    seen, selected = {fingerprint(p) for p in exclude_prompts}, []
    for _, _, question in eligible:
        key = fingerprint(question.prompt)
        if key not in seen:
            selected.append(question)
            seen.add(key)
            if len(selected) == limit:
                break
    return selected


async def top_up_prepared_bank(db: AsyncSession, user_id: str, task, draft) -> bool:
    """Let an old failed draft benefit from newly published content on retry."""
    missing = 50 - len(draft.bank_ids) - len(draft.questions)
    if missing <= 0:
        return False
    existing_prompts = list(
        await db.scalars(select(Question.prompt).where(Question.id.in_(draft.bank_ids)))
    )
    additions = await choose_prepared_questions(
        db,
        user_id,
        task,
        exclude_ids=draft.bank_ids,
        exclude_prompts=[*existing_prompts, *(q["prompt"] for q in draft.questions)],
        limit=missing,
    )
    if not additions:
        return False
    draft.bank_ids = [*draft.bank_ids, *(q.id for q in additions)]
    # Pending candidates were never counted as checked. Keep them if more are
    # needed; discard only a surplus when a full checked set is already ready.
    remaining = 50 - len(draft.bank_ids) - len(draft.questions)
    draft.pending_questions = list(draft.pending_questions)[:remaining]
    if remaining == 0:
        draft.failure_count, draft.next_retry_at = 0, None
    return True
