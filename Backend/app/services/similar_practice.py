"""Personal CDS-level sets, separate from the shared bank and official keys."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.practice import AttemptQuestion, PracticeAttempt, Question, Subject, Topic
from app.models.study_plan import DailyQuizPreparation, DailyStudyPlan, DailyStudyTask
from app.schemas.practice import (
    AttemptResponse,
    PracticeQuestionResponse,
    StartSimilarAttemptRequest,
)
from app.services.practice_sets import (
    PracticeQuestion,
    PracticeUnavailableError,
    generate_practice_set,
)
from app.services.rag import RagService, RagUnavailableError
from app.services.study_memory import locked_profile


async def create_similar_attempt(
    db: AsyncSession,
    user_id: str,
    payload: StartSimilarAttemptRequest,
    rag: RagService,
    *,
    daily_task_id: str | None = None,
    bank_questions: list[Question] | None = None,
) -> AttemptResponse:
    bank_questions = bank_questions or []
    subject = await db.scalar(select(Subject).where(Subject.slug == payload.subject_slug))
    if not subject:
        raise HTTPException(404, "Subject not found")
    topics = list(await db.scalars(select(Topic).where(Topic.subject_id == subject.id)))
    selected = next((item for item in topics if item.slug == payload.topic_slug), None)
    if payload.topic_slug and not selected:
        raise HTTPException(404, "Topic not found for this subject")
    # Fresh news cannot be made accurate by guessing. Keep generated sets to static syllabus.
    allowed = [
        item for item in ([selected] if selected else topics) if not item.slug.startswith("current")
    ]
    if not allowed:
        raise HTTPException(
            422,
            "Use the question bank for current affairs. "
            "Choose a static topic for similar practice.",
        )
    topic_by_slug = {item.slug: item for item in allowed}
    recent_prompts = list(
        await db.scalars(
            select(Question.prompt)
            .where(
                Question.owner_user_id == user_id,
                Question.topic_id.in_([item.id for item in allowed]),
            )
            .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
            .join(PracticeAttempt, PracticeAttempt.id == AttemptQuestion.attempt_id)
            .order_by(PracticeAttempt.started_at.desc(), AttemptQuestion.position)
            .limit(1000)
        )
    )
    # The shared generator includes the last 50 prompts in its avoid-list.
    recent_prompts.reverse()
    seeds = list(
        await db.scalars(
            select(Question)
            .where(
                Question.owner_user_id.is_(None),
                Question.is_active.is_(True),
                Question.topic_id.in_([item.id for item in allowed]),
            )
            .order_by(func.random())
            .limit(8)
        )
    )
    focus = selected.name if selected else f"mixed {subject.name} syllabus"
    if payload.focus_detail:
        focus += ": " + payload.focus_detail
    topic_names = {slug: topic.name for slug, topic in topic_by_slug.items()}
    profile = await locked_profile(db, user_id)
    now = datetime.now(UTC)
    if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) > now:
        raise HTTPException(429, "Please wait for your current set or answer to finish.")
    if not profile.request_window_started or (
        now - profile.request_window_started.replace(tzinfo=UTC) >= timedelta(minutes=1)
    ):
        profile.request_window_started = now
        profile.requests_in_window = 0
    if profile.requests_in_window >= 4:
        raise HTTPException(429, "Please wait a minute before creating another set.")
    used_today = await db.scalar(
        select(func.coalesce(func.sum(PracticeAttempt.total_questions), 0)).where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.question_mode.in_(["similar", "daily"]),
            PracticeAttempt.started_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
    )
    # A resumable daily draft has already reserved its full set, even before its
    # final attempt exists. Other generation routes must respect that reservation.
    reserved = await db.scalar(
        select(func.count())
        .select_from(DailyQuizPreparation)
        .join(DailyStudyTask)
        .join(DailyStudyPlan)
        .where(
            DailyStudyPlan.user_id == user_id,
            DailyQuizPreparation.attempt_id.is_(None),
            DailyQuizPreparation.created_at
            >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
    )
    used_today += reserved * 50
    requested_total = payload.question_count + len(bank_questions)
    if used_today + requested_total > get_settings().practice_ai_daily_questions:
        raise HTTPException(
            429,
            "Today's similar-practice limit is reached. "
            "You can still practise the question bank or resume saved sets.",
        )
    profile.requests_in_window += 1
    lease_until = now + timedelta(seconds=165)
    profile.busy_until = lease_until
    await db.commit()  # Never hold a row lock or an open transaction while waiting on AI.
    committed = False
    try:

        async def generate(prompt: str) -> dict:
            instructions = f"""
This is a scored CDS/OTA exam-level set for {subject.name}, not a beginner quiz.
Use mostly moderate and challenging exam-style items with plausible distractors.
English: use nuanced grammar, contextual vocabulary, idioms, and sentence reasoning.
Write each question as a FULL, explicit instruction followed by its sentence or passage.
For example: "Choose the correct word to complete the sentence: ..." or
"Identify the part containing a grammatical error in the sentence: ...".
Test conditionals, inversion, parallelism, agreement, modifiers and contextual word use.
For synonyms/antonyms explicitly name the word and whether a synonym or antonym is needed.
Do not output isolated word pairs or fragments copied from a larger paper's directions.
Reading questions require a complete short passage and a specific inference question.
GK: use CDS-style statement/comparison questions, not only one-line trivia.
Maths: include multi-step school-syllabus problems and reasonable calculation demands.
Questions must be self-contained. Include any required passage in the prompt.
Ask the task explicitly (synonym/antonym/error/meaning/etc.). Do not give only a sentence
or word-pair without a question. Do not refer to underlined/highlighted words: name the
target word explicitly. Word-matching questions must have a valid meaning for every entry.
Solve each question first to check its answer; exactly one option must be correct.
Spread correct answer positions. Never claim these are actual UPSC questions.
Each item MUST include topic_slug, chosen accurately from: {json.dumps(topic_names)}.
Use the standard CDS syllabus and examination depth, not beginner trivia or copied PYQs.
"""
            requested = int(re.search(r"Create exactly (\d+)", prompt)[1])
            candidates = []
            # Prepare manageable batches for reliable generation and independent review;
            # users still receive ONE full set of the requested size.
            # The shared validator deduplicates/repairs the combined result before saving.
            for offset in range(0, requested, 25):
                batch_count = min(25, requested - offset)
                batch_prompt = re.sub(
                    r"Create exactly \d+", f"Create exactly {batch_count}", prompt, count=1
                )
                batch_prompt += instructions
                if candidates:
                    batch_prompt += (
                        "\nContinue with different concepts. Do not repeat: "
                        + json.dumps([item["prompt"] for item in candidates], ensure_ascii=False)
                    )
                try:
                    raw = await rag.generate_similar_questions(batch_prompt, list(topic_names))
                except (RagUnavailableError, TimeoutError):
                    if candidates:
                        break  # Review earlier candidates instead of discarding them.
                    raise
                received = raw.get("questions", [])
                if isinstance(received, list):
                    for item in received[:batch_count]:
                        try:
                            checked = PracticeQuestion.model_validate(item).model_dump()
                            if (
                                checked["topic_slug"] in topic_by_slug
                                and not re.search(
                                    r"underlined|highlighted", checked["prompt"], re.IGNORECASE
                                )
                                and re.search(
                                    r"\?|\b(?:choose|select|which|what|identify|spot|determine|find|"
                                    r"compute|calculate|arrange|match|complete)\b",
                                    checked["prompt"],
                                    re.IGNORECASE,
                                )
                            ):
                                candidates.append(checked)
                        except ValidationError:
                            continue
            items = []
            if candidates:
                # One combined independent review sees duplicates across batches and
                # uses fewer provider requests. Unreviewed items are NEVER returned.
                review = (
                    await rag.review_similar_questions(
                        candidates, focus_detail=payload.focus_detail
                    )
                    if daily_task_id
                    else await rag.review_similar_questions(candidates)
                )
                reviews = review.get("reviews", [])
                judgments = {}
                if isinstance(reviews, list):
                    for judgment in reviews:
                        if not isinstance(judgment, dict):
                            continue
                        number = judgment.get("number")
                        if type(number) is int:
                            # Duplicate judgments are invalid, never "last answer wins".
                            judgments[number] = None if number in judgments else judgment
                for number, item in enumerate(candidates, start=1):
                    judgment = judgments.get(number)
                    if (
                        judgment
                        and judgment.get("usable") is True
                        and type(judgment.get("answer_index")) is int
                        and judgment["answer_index"] == item["correct_index"]
                    ):
                        items.append(item)
            return {"questions": items}

        async with asyncio.timeout(150):
            generated = await generate_practice_set(
                generate,
                f"Create {payload.question_count} questions",
                [],
                subject=subject.name,
                repair_attempts=3,
                previous={
                    "topic": focus,
                    "questions": [{"prompt": q.prompt} for q in seeds]
                    + [{"prompt": p} for p in recent_prompts]
                    + [{"prompt": q.prompt} for q in bank_questions],
                },
            )
        if len(generated["questions"]) != payload.question_count:
            raise PracticeUnavailableError(
                "The full set couldn't be prepared. Try a smaller set or use the question bank."
            )
        daily_task = None
        if daily_task_id:
            from app.models.auth import User
            from app.services.daily_quiz import ready_task

            await db.execute(select(User.id).where(User.id == user_id).with_for_update())
            daily_task = await ready_task(db, user_id, daily_task_id)
            if daily_task.quiz_attempt and daily_task.quiz_attempt.status == "in_progress":
                raise HTTPException(
                    409, "This quiz is already open. Return to today's plan to resume it."
                )
        total = payload.question_count + len(bank_questions)
        if daily_task_id and total != 50:
            raise PracticeUnavailableError(
                "The full 50-question quiz could not be prepared. Please try again."
            )
        attempt = PracticeAttempt(
            user_id=user_id,
            subject_id=subject.id,
            topic_id=selected.id if selected else None,
            total_questions=total,
            time_limit_seconds=total * (72 if subject.slug == "elementary-mathematics" else 60),
            negative_mark_fraction=1 / 3,
            question_mode="daily" if daily_task_id else "similar",
        )
        db.add(attempt)
        await db.flush()
        questions = []
        for position, question in enumerate(bank_questions, start=1):
            db.add(
                AttemptQuestion(attempt_id=attempt.id, question_id=question.id, position=position)
            )
            questions.append(
                PracticeQuestionResponse(
                    id=question.id,
                    position=position,
                    subject=subject.name,
                    topic=selected.name if selected else subject.name,
                    prompt=question.prompt,
                    context=question.context,
                    options=question.options,
                    source_label=question.source_label,
                    provenance=question.provenance,
                )
            )
        for position, item in enumerate(generated["questions"], start=1 + len(bank_questions)):
            topic = topic_by_slug[item["topic_slug"]]
            question = Question(
                topic_id=topic.id,
                owner_user_id=user_id,
                prompt=item["prompt"],
                context=None,
                options=item["options"],
                correct_index=item["correct_index"],
                explanation=item["explanation"],
                difficulty="cds",
                source_label="AI-created CDS-style practice",
                provenance={"kind": "generated", "answer_verified": False},
            )
            db.add(question)
            await db.flush()
            db.add(
                AttemptQuestion(attempt_id=attempt.id, question_id=question.id, position=position)
            )
            questions.append(
                PracticeQuestionResponse(
                    id=question.id,
                    position=position,
                    subject=subject.name,
                    topic=topic.name,
                    prompt=question.prompt,
                    context=None,
                    options=question.options,
                    source_label=question.source_label,
                    provenance=question.provenance,
                )
            )
        if daily_task:
            if daily_task.quiz_attempt and daily_task.quiz_attempt.status == "completed":
                daily_task.previous_quiz_answered += len(daily_task.quiz_attempt.answers)
                daily_task.previous_quiz_correct += sum(
                    a.is_correct for a in daily_task.quiz_attempt.answers
                )
            daily_task.quiz_attempt = attempt
        profile = await locked_profile(db, user_id)
        if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) == lease_until:
            profile.busy_until = None
        await db.commit()
        committed = True
        return AttemptResponse(
            id=attempt.id,
            subject=subject.name,
            subject_slug=subject.slug,
            topic=selected.name if selected else None,
            topic_slug=selected.slug if selected else None,
            started_at=attempt.started_at,
            duration_seconds=attempt.time_limit_seconds,
            negative_mark_fraction=attempt.negative_mark_fraction,
            question_mode=attempt.question_mode,
            new_questions=len(questions),
            questions=questions,
        )
    except (PracticeUnavailableError, RagUnavailableError, TimeoutError) as exc:
        detail = (
            "We couldn't prepare all 50 questions right now. Your study progress is saved. "
            "Please try again in a little while."
            if daily_task_id
            else "Similar practice has reached its AI usage limit. Try again later, "
            "or use Unanswered questions or Mixed revision."
            if "rate-limited" in str(exc)
            else str(exc)
            if str(exc)
            else "Preparing your set took too long. Try again or choose a smaller set."
        )
        raise HTTPException(503, detail) from exc
    finally:
        if not committed:
            await db.rollback()
            profile = await locked_profile(db, user_id)
            if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) == lease_until:
                profile.busy_until = None
            await db.commit()
