import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.rag import DoubtStudyProfile
from app.schemas.doubts import StudyProfileResponse, StudyTopic

# Only these academic categories are persisted, never inferred personal traits.
TOPICS = {
    "Polity": (r"constitution|fundamental rights|parliament|polity|article \d+",
               "Explain Fundamental Rights with a CDS example"),
    "Geography": (r"weather|climate|geography|river|monsoon|latitude",
                  "Quiz me on weather and climate"),
    "Time and work": (r"time and work|workers|pipes|cistern|efficien",
                      "Show me a shortcut for a time and work question"),
    "Algebra": (r"algebra|equation|quadratic|polynomial|solve.*[=]",
                "Walk me through a quadratic equation"),
    "Geometry": (r"geometry|triangle|circle|angle|perimeter|area",
                 "Explain a useful triangle theorem with an example"),
    "Arithmetic": (r"percent|ratio|profit|interest|average|arithmetic",
                   "Give me a CDS percentage question with a solution"),
    "English": (r"english|grammar|vocabulary|synonym|antonym|idiom|tense|preposition",
                "Help me practise CDS English error spotting"),
    "History": (r"history|empire|revolt|independence|mughal|civilization",
                "Quiz me on the Indian freedom movement"),
    "Science": (r"physics|chemistry|biology|newton|force|momentum|cell|electric|photosynthesis",
                "Explain Newton's laws with everyday examples"),
    "Previous papers": (r"previous paper|past paper|pyq|cds.*20\d\d|20\d\d.*cds",
                        "Help me revise topics from recent CDS papers"),
}
DEFAULT_SUGGESTIONS = [TOPICS[key][1] for key in ("Polity", "Time and work", "Geography")]
STYLE_INSTRUCTIONS = {
    "step-by-step": "Explain in clear numbered steps, with a short worked example when useful.",
    "concise": "Keep the explanation brief: the key idea, essential working, and the answer.",
    "hints-first": "Give a useful hint and guiding question before revealing the full solution.",
}


async def locked_profile(db: AsyncSession, user_id: str) -> DoubtStudyProfile:
    # The user row also serializes first-time profile creation across workers on PostgreSQL.
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = (await db.execute(
        select(DoubtStudyProfile).where(DoubtStudyProfile.user_id == user_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if profile is None:
        profile = DoubtStudyProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
    return profile


def remember_question(profile: DoubtStudyProfile, question: str, subject: str | None) -> None:
    if not profile.enabled:
        return
    counts = dict(profile.topic_counts)
    matched = [topic for topic, (pattern, _) in TOPICS.items()
               if re.search(pattern, question, re.IGNORECASE)]
    if not matched and subject == "english":
        matched = ["English"]
    for topic in matched:
        counts[topic] = min(counts.get(topic, 0) + 1, 1_000_000)
    profile.topic_counts = counts
    profile.total_questions += 1


def profile_response(profile: DoubtStudyProfile | None) -> StudyProfileResponse:
    topics = sorted((profile.topic_counts if profile else {}).items(),
                    key=lambda item: (-item[1], item[0]))
    enabled = profile.enabled if profile else True
    suggestions = [TOPICS[name][1] for name, _ in topics if name in TOPICS] if enabled else []
    for suggestion in DEFAULT_SUGGESTIONS:
        if suggestion not in suggestions:
            suggestions.append(suggestion)
    return StudyProfileResponse(
        enabled=enabled,
        explanation_style=profile.explanation_style if profile else "step-by-step",
        topics=[StudyTopic(name=name, count=count) for name, count in topics[:8]],
        total_questions=profile.total_questions if profile else 0,
        suggested_questions=suggestions[:3],
    )


def tutor_context(profile: DoubtStudyProfile) -> str:
    if not profile.enabled:
        return "No saved study preferences."
    topics = sorted(profile.topic_counts, key=lambda name: -profile.topic_counts[name])[:3]
    return (
        STYLE_INSTRUCTIONS.get(profile.explanation_style, STYLE_INSTRUCTIONS["step-by-step"])
        + "\nRecently studied topics: " + (", ".join(topics) or "None yet")
        + ". Use relevant familiar examples, but prioritize the latest question. "
        "Do not assume these topics are weaknesses or disclose memory unless asked."
    )
