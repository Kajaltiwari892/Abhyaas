"""Build a notebook from completed attempts, including skipped assignments.

Window queries collapse repeated attempts before pagination. Imported practice
PYQs share the paper-question identity, so solving the same PYQ in two places
does not create two notebook entries. Bank answers keep their original keys;
similar practice retains its AI-created label and saved answer/explanation.
"""

from sqlalchemy import and_, case, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.papers import PaperAnswer, PaperAttempt, PaperQuestion, PreviousPaper
from app.models.practice import AttemptQuestion, PracticeAnswer, PracticeAttempt, Question, Topic
from app.models.revision import RevisionAnswer, RevisionSession
from app.services.paper_answers import stored_answer
from app.services.practice_catalog import prepare_question


async def notebook_entries(db: AsyncSession, user_id: str):
    # Resolve current keys first: old attempts must gain newly reviewed answers,
    # and edits to the question must invalidate a text-bound review everywhere.
    candidates = (
        await db.execute(
            select(PaperQuestion, PreviousPaper)
            .join(PreviousPaper, PreviousPaper.id == PaperQuestion.paper_id)
            .where(
                PreviousPaper.id.in_(
                    select(PaperAttempt.paper_id).where(
                        PaperAttempt.user_id == user_id,
                        PaperAttempt.status == "completed",
                    )
                )
            )
        )
    ).all()
    keys = {q.id: key.index for q, p in candidates if (key := stored_answer(q, p))}
    current_index = case(keys, value=PaperQuestion.id, else_=None) if keys else literal(None)
    paper_id = Question.provenance["paper_question_id"].as_string()
    practice_key = case(
        (
            and_(Question.provenance["kind"].as_string() == "pyq", paper_id.is_not(None)),
            literal("paper:") + paper_id,
        ),
        else_=literal("practice:") + Question.id,
    )
    practice = (
        select(
            practice_key.label("question_key"),
            Question.id.label("question_id"),
            literal("practice").label("kind"),
            PracticeAttempt.subject_id.label("subject_id"),
            PracticeAttempt.id.label("attempt_id"),
            PracticeAttempt.completed_at.label("completed_at"),
            PracticeAnswer.selected_index.label("selected_index"),
            func.coalesce(PracticeAnswer.is_correct, False).label("is_correct"),
        )
        .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
        .join(PracticeAttempt, PracticeAttempt.id == AttemptQuestion.attempt_id)
        .outerjoin(
            PracticeAnswer,
            and_(
                PracticeAnswer.attempt_id == PracticeAttempt.id,
                PracticeAnswer.question_id == Question.id,
            ),
        )
        .where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.status == "completed",
            PracticeAttempt.completed_at.is_not(None),
        )
    )
    papers = (
        select(
            (literal("paper:") + PaperQuestion.id).label("question_key"),
            PaperQuestion.id.label("question_id"),
            literal("paper").label("kind"),
            PreviousPaper.subject_id.label("subject_id"),
            PaperAttempt.id.label("attempt_id"),
            PaperAttempt.completed_at.label("completed_at"),
            PaperAnswer.selected_index.label("selected_index"),
            func.coalesce(PaperAnswer.selected_index == current_index, False).label("is_correct"),
        )
        .join(PreviousPaper, PreviousPaper.id == PaperQuestion.paper_id)
        .join(PaperAttempt, PaperAttempt.paper_id == PreviousPaper.id)
        .outerjoin(
            PaperAnswer,
            and_(
                PaperAnswer.attempt_id == PaperAttempt.id,
                PaperAnswer.question_id == PaperQuestion.id,
            ),
        )
        .where(
            PaperAttempt.user_id == user_id,
            PaperAttempt.status == "completed",
            PaperAttempt.completed_at.is_not(None),
            PaperQuestion.id.in_(keys),
        )
    )
    events = union_all(practice, papers).subquery("notebook_events")
    ordering = (events.c.completed_at.desc(), events.c.attempt_id.desc())
    ranked = select(
        events,
        func.row_number().over(partition_by=events.c.question_key, order_by=ordering).label("rn"),
        func.max(case((events.c.is_correct.is_(False), 1), else_=0))
        .over(partition_by=events.c.question_key)
        .label("had_mistake"),
    ).subquery("ranked_attempts")
    faults = (
        select(
            events.c.question_key,
            events.c.selected_index,
            func.row_number()
            .over(partition_by=events.c.question_key, order_by=ordering)
            .label("rn"),
        )
        .where(events.c.is_correct.is_(False))
        .subquery("latest_faults")
    )
    retries = (
        select(
            RevisionAnswer.question_key,
            RevisionAnswer.is_correct,
            RevisionAnswer.selected_index,
            RevisionSession.completed_at,
            func.row_number()
            .over(
                partition_by=RevisionAnswer.question_key,
                order_by=(RevisionSession.completed_at.desc(), RevisionSession.id.desc()),
            )
            .label("rn"),
        )
        .join(RevisionSession, RevisionSession.id == RevisionAnswer.session_id)
        .where(
            RevisionSession.user_id == user_id,
            RevisionSession.status == "completed",
        )
        .subquery("latest_retries")
    )
    effective_correct = case(
        (retries.c.completed_at >= ranked.c.completed_at, retries.c.is_correct),
        else_=ranked.c.is_correct,
    )
    effective_choice = case(
        (retries.c.completed_at >= ranked.c.completed_at, retries.c.selected_index),
        else_=ranked.c.selected_index,
    )
    return (
        select(
            ranked.c.question_key,
            ranked.c.question_id,
            ranked.c.kind,
            ranked.c.subject_id,
            ranked.c.completed_at,
            effective_choice.label("selected_index"),
            case((faults.c.selected_index.is_(None), "skipped"), else_="wrong").label("reason"),
            case((effective_correct.is_(True), "resolved"), else_="pending").label("state"),
        )
        .outerjoin(
            retries, and_(retries.c.question_key == ranked.c.question_key, retries.c.rn == 1)
        )
        .join(faults, and_(faults.c.question_key == ranked.c.question_key, faults.c.rn == 1))
        .where(ranked.c.rn == 1, ranked.c.had_mistake == 1)
        .subquery("notebook_entries")
    )


def safe_source(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith("https://") or value.startswith("/papers/"):
        return value
    return None


async def question_snapshots(db: AsyncSession, rows) -> list[dict]:
    practice_ids = [row.question_id for row in rows if row.kind == "practice"]
    paper_ids = [row.question_id for row in rows if row.kind == "paper"]
    practice = (
        {
            q.id: q
            for q in (
                await db.scalars(
                    select(Question)
                    .where(Question.id.in_(practice_ids))
                    .options(selectinload(Question.topic).selectinload(Topic.subject))
                )
            ).all()
        }
        if practice_ids
        else {}
    )
    papers = (
        {
            q.id: q
            for q in (
                await db.scalars(
                    select(PaperQuestion)
                    .where(PaperQuestion.id.in_(paper_ids))
                    .options(
                        selectinload(PaperQuestion.paper).selectinload(PreviousPaper.subject),
                        selectinload(PaperQuestion.topic),
                    )
                )
            ).all()
        }
        if paper_ids
        else {}
    )
    snapshots = []
    for row in rows:
        if row.kind == "practice":
            q = practice.get(row.question_id)
            if not q:
                continue
            subject = q.topic.subject
            provenance = q.provenance or {}
            review_available = bool(q.prompt.strip()) and (
                2 <= len(q.options) <= 10
                and 0 <= q.correct_index < len(q.options)
                and all(isinstance(option, str) and option.strip() for option in q.options)
            )
            ready = q.is_active and review_available
            data = dict(
                prompt=q.prompt,
                context=q.context,
                options=q.options,
                topic=q.topic.name,
                correct_index=q.correct_index,
                explanation=q.explanation,
                source_label=q.source_label,
                source_url=safe_source(provenance.get("source_url")),
                source_page_url=safe_source(provenance.get("source_page_url")),
            )
        else:
            q = papers.get(row.question_id)
            if not q:
                continue
            subject = q.paper.subject
            key = stored_answer(q, q.paper)
            if key is None:
                continue
            prepared, _ = prepare_question(q, q.paper, subject.slug)
            record = q.transcription or {}
            context = (
                "\n\n".join(
                    dict.fromkeys(
                        str(record[key]).strip()
                        for key in ("sectionTitle", "directions", "passage")
                        if record.get(key)
                    )
                )
                or q.context
            )
            ready = prepared is not None
            review_available = ready
            data = dict(
                prompt=record.get("prompt") or q.prompt,
                context=context,
                options=record.get("options") or q.options,
                topic=q.topic.name if q.topic else "Mixed topics",
                correct_index=key.index,
                explanation=key.explanation,
                source_label=(
                    f"CDS {q.paper.cycle} {q.paper.year} · Q{q.number} · {key.source_label}"
                ),
                source_url=safe_source(q.paper.source_url),
                source_page_url=safe_source(record.get("sourcePageUrl")),
            )
            if prepared:
                data.update(
                    prompt=prepared["prompt"],
                    context=prepared["context"],
                    options=prepared["options"],
                )
        snapshots.append(
            dict(
                question_key=row.question_key,
                subject=subject.name,
                subject_slug=subject.slug,
                reason=row.reason,
                state=row.state,
                last_attempt_at=row.completed_at.isoformat(),
                selected_index=row.selected_index,
                revision_ready=bool(ready),
                review_available=bool(review_available),
                **data,
            )
        )
    return snapshots


def public_revision_question(question: dict) -> dict:
    # An explicit allowlist: do not leak answer keys, explanations or old choices.
    return {
        key: question[key]
        for key in (
            "question_key",
            "subject",
            "subject_slug",
            "topic",
            "prompt",
            "context",
            "options",
            "source_label",
            "source_url",
            "source_page_url",
        )
    }


async def revision_questions(db: AsyncSession, query, entries, count: int) -> list[dict]:
    # The notebook already selected current scorable keys. Validate complete text
    # before including any paper question in a new revision set.
    paper_ids = (
        select(PaperQuestion.id)
        .join(PreviousPaper)
        .where(
            PreviousPaper.is_published.is_(True),
        )
    )
    query = query.where(
        or_(
            and_(
                entries.c.kind == "practice",
                entries.c.question_id.in_(select(Question.id).where(Question.is_active.is_(True))),
            ),
            and_(entries.c.kind == "paper", entries.c.question_id.in_(paper_ids)),
        )
    ).order_by(entries.c.completed_at, entries.c.question_key)
    questions = []
    offset = 0
    while len(questions) < count:
        rows = (await db.execute(query.offset(offset).limit(100))).all()
        if not rows:
            break
        questions.extend(q for q in await question_snapshots(db, rows) if q["revision_ready"])
        offset += len(rows)
        if len(rows) < 100:
            break
    return questions[:count]
