import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.auth import User, utc_now
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.rag import DoubtConversation, DoubtMessage, DoubtStudyProfile
from app.schemas.doubts import (
    AskDoubtRequest,
    AskDoubtResponse,
    DoubtConversationResponse,
    DoubtMessageResponse,
    DoubtSourceResponse,
    StudyProfileResponse,
    StudyProfileUpdate,
)
from app.services.doubt_images import normalize_image
from app.services.question_bank import question_card
from app.services.question_requests import requested_count, wants_all
from app.services.rag import RagService, RagUnavailableError, get_rag_service, source_to_dict
from app.services.study_memory import (
    locked_profile,
    profile_response,
    remember_question,
    tutor_context,
)

router = APIRouter(prefix="/doubts", tags=["doubt solver"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
RagDependency = Annotated[RagService, Depends(get_rag_service)]


async def owned_conversation(
    db: AsyncSession, conversation_id: str, user_id: str
) -> DoubtConversation:
    conversation = (
        await db.execute(
            select(DoubtConversation).where(
                DoubtConversation.id == conversation_id,
                DoubtConversation.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Doubt conversation not found")
    return conversation


@router.post("/ask", response_model=AskDoubtResponse)
async def ask_doubt(
    payload: AskDoubtRequest,
    user: CurrentUser,
    db: DatabaseSession,
    rag: RagDependency,
) -> AskDoubtResponse:
    user_id = user.id  # Keep a scalar available even after a transaction rollback.
    question = " ".join(payload.question.split())
    if not question and payload.image:
        question = "Please explain and solve the question in this image."
    if len(question) < 3:
        raise HTTPException(status_code=422, detail="Please enter a complete question")

    if payload.conversation_id:
        await owned_conversation(db, payload.conversation_id, user_id)
    # Larger, bounded sets need time for several provider batches. The lease must
    # outlive that budget; a second request must not overlap a still-running set.
    processing_seconds = 150 if (requested_count(question) or 0) > 10 or wants_all(question) else 75
    if payload.conversation_id:
        pending_practice = await db.scalar(
            select(DoubtMessage.practice_result)
            .where(
                DoubtMessage.conversation_id == payload.conversation_id,
                DoubtMessage.role == "assistant",
            )
            .order_by(DoubtMessage.created_at.desc())
            .limit(1)
        )
        if pending_practice and pending_practice.get("kind") == "clarification":
            processing_seconds = 150
    profile = await locked_profile(db, user_id)
    now = datetime.now(UTC)
    busy_until = profile.busy_until
    if busy_until and busy_until.replace(tzinfo=UTC) > now:
        raise HTTPException(
            status_code=429, detail="Please wait for your current answer to finish."
        )
    window = profile.request_window_started
    if not window or now - window.replace(tzinfo=UTC) >= timedelta(minutes=1):
        profile.request_window_started = now
        profile.requests_in_window = 0
    if profile.requests_in_window >= 4:
        raise HTTPException(status_code=429, detail="Please wait a minute before asking again.")

    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    used_today = (
        await db.execute(
            select(func.count(DoubtMessage.id))
            .join(DoubtConversation)
            .where(
                DoubtConversation.user_id == user_id,
                DoubtMessage.role == "user",
                DoubtMessage.created_at >= day_start,
            )
        )
    ).scalar_one()
    if used_today >= get_settings().rag_daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Your daily doubt-solver limit has been reached. Try again tomorrow.",
        )

    # Reserve before any image decoding or AI call. Failed attempts still count toward burst limits.
    profile.requests_in_window += 1
    lease_until = now + timedelta(seconds=processing_seconds + 15)
    profile.busy_until = lease_until
    personalization = tutor_context(profile)
    await db.commit()
    completed = False
    try:
        async with asyncio.timeout(processing_seconds):
            image_data = None
            if payload.image:
                try:
                    image_data = await asyncio.to_thread(
                        normalize_image, payload.image.data, payload.image.mime_type
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            if payload.conversation_id:
                conversation = await owned_conversation(db, payload.conversation_id, user_id)
                recent = list(
                    (
                        await db.execute(
                            select(DoubtMessage)
                            .where(DoubtMessage.conversation_id == conversation.id)
                            .order_by(DoubtMessage.created_at.desc())
                            .limit(6)
                        )
                    ).scalars()
                )
                history = [(message.role, message.content) for message in reversed(recent)]
                # Only the latest assistant turn can supply follow-up filters: do not revive
                # a stale PYQ search after an unrelated conversation.
                last_reply = next(
                    (message for message in recent if message.role == "assistant"), None
                )
                pyq_context = last_reply.pyq_result if last_reply else None
                practice_context = last_reply.practice_result if last_reply else None
            else:
                conversation = None
                history = []
                pyq_context = None
                practice_context = None
            recognized = await rag.read_question_image(image_data) if image_data else ""
            effective_question = (
                f"{question}\n\nQuestion visible in the attached image:\n{recognized}"
                if recognized
                else question
            )
            if payload.paper_question_id:
                item = (
                    await db.execute(
                        select(PaperQuestion, PreviousPaper)
                        .join(PreviousPaper)
                        .options(selectinload(PreviousPaper.subject))
                        .where(
                            PaperQuestion.id == payload.paper_question_id,
                            PreviousPaper.is_published.is_(True),
                        )
                    )
                ).first()
                if not item or not item[0].transcription:
                    raise HTTPException(status_code=404, detail="Source question not available")
                card = question_card(*item)
                if card["has_visual"] and not image_data:
                    raise HTTPException(
                        status_code=422,
                        detail="Attach the original diagram so I can explain it accurately.",
                    )
                options = "\n".join(
                    f"{chr(65 + i)}. {text}" for i, text in enumerate(card["options"])
                )
                key_note = (
                    f"Verified answer-key index (A=0): {card['correct_index']}."
                    if card["answer_verified"]
                    else "No verified key is available. Label solutions as AI reasoning, "
                    "not an official answer."
                )
                effective_question = (
                    f"{question}\n\nExplain this stored CDS {card['cycle']} {card['year']} "
                    f"{card['subject']} Q{card['number']}.\n{card.get('passage') or ''}\n"
                    f"{card.get('directions') or ''}\n{card['prompt']}\n{options}\n{key_note}"
                )
            result = await rag.answer(
                db,
                effective_question,
                payload.subject,
                history,
                personalization=personalization,
                image_data=image_data,
                pyq_context=pyq_context,
                practice_context=practice_context,
                explaining_paper_question=bool(payload.paper_question_id),
            )
            citations = [source_to_dict(source) for source in result.sources]
            # Do not hold a new conversation's user-FK lock while waiting on the AI provider.
            # Memory controls must remain responsive while an answer is being generated.
            profile = await locked_profile(db, user_id)
            if conversation is None:
                conversation = DoubtConversation(user_id=user_id, title=question[:117])
                db.add(conversation)
                await db.flush()
            db.add(
                DoubtMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=effective_question,
                    citations=[],
                )
            )
            db.add(
                DoubtMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=result.answer,
                    citations=citations,
                    confidence=result.confidence,
                    pyq_result=result.pyq_result,
                    practice_result=result.practice_result,
                )
            )
            conversation.updated_at = utc_now()
            remember_question(profile, effective_question, payload.subject)
            profile.busy_until = None
            await db.commit()
            completed = True
        return AskDoubtResponse(
            conversation_id=conversation.id,
            answer=result.answer,
            confidence=result.confidence,
            grounded=bool(result.sources)
            or bool(result.pyq_result and result.pyq_result["questions"]),
            sources=[DoubtSourceResponse.model_validate(source) for source in citations],
            follow_up_questions=result.follow_up_questions,
            pyq_result=result.pyq_result,
            practice_result=result.practice_result,
            answer_kind=result.answer_kind,
        )
    except (RagUnavailableError, TimeoutError) as exc:
        detail = (
            str(exc)
            if isinstance(exc, RagUnavailableError)
            else ("The answer took too long. Please try again with a shorter question.")
        )
        raise HTTPException(status_code=503, detail=detail) from exc
    finally:
        if not completed:
            await db.rollback()
            profile = await locked_profile(db, user_id)
            # Never release a newer request's lease after an expired/cancelled request.
            if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) == lease_until:
                profile.busy_until = None
            await db.commit()


@router.get("/personalization", response_model=StudyProfileResponse)
async def get_personalization(user: CurrentUser, db: DatabaseSession) -> StudyProfileResponse:
    return profile_response(await db.get(DoubtStudyProfile, user.id))


@router.patch("/personalization", response_model=StudyProfileResponse)
async def update_personalization(
    payload: StudyProfileUpdate,
    user: CurrentUser,
    db: DatabaseSession,
) -> StudyProfileResponse:
    profile = await locked_profile(db, user.id)
    if payload.enabled is not None:
        profile.enabled = payload.enabled
    if payload.explanation_style is not None:
        profile.explanation_style = payload.explanation_style
    await db.commit()
    return profile_response(profile)


@router.delete("/personalization", response_model=StudyProfileResponse)
async def clear_personalization(user: CurrentUser, db: DatabaseSession) -> StudyProfileResponse:
    profile = await locked_profile(db, user.id)
    profile.topic_counts = {}
    profile.total_questions = 0
    profile.explanation_style = "step-by-step"
    await db.commit()
    return profile_response(profile)


@router.get("/conversations/{conversation_id}", response_model=DoubtConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: CurrentUser,
    db: DatabaseSession,
) -> DoubtConversationResponse:
    conversation = (
        await db.execute(
            select(DoubtConversation)
            .options(selectinload(DoubtConversation.messages))
            .where(
                DoubtConversation.id == conversation_id,
                DoubtConversation.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Doubt conversation not found")
    return DoubtConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            DoubtMessageResponse(
                id=message.id,
                role=message.role,
                content=message.content,
                citations=[
                    DoubtSourceResponse.model_validate(citation) for citation in message.citations
                ],
                confidence=message.confidence,
                created_at=message.created_at,
                pyq_result=message.pyq_result,
                practice_result=message.practice_result,
            )
            for message in conversation.messages
        ],
    )
