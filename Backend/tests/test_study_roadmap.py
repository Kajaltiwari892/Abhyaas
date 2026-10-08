from datetime import date

from app.models.practice import Question
from app.services.daily_quiz import matches_lesson
from app.services.study_curriculum import CURRICULUM, build_roadmap, coverage_deadline, find_unit

OTA = ["english", "general-knowledge"]


def test_two_calendar_months_not_sixty_days():
    assert coverage_deadline(date(2027, 4, 11)) == date(2027, 2, 11)
    assert coverage_deadline(date(2027, 4, 30)) == date(2027, 2, 28)
    assert coverage_deadline(date(2028, 4, 30)) == date(2028, 2, 29)
    assert coverage_deadline(date(2027, 1, 31)) == date(2026, 11, 30)


def test_full_ota_syllabus_is_dated_and_time_budgeted_before_deadline():
    today = date(2026, 10, 8)
    result = build_roadmap(today, date(2027, 4, 11), 120, OTA, set(), today)
    assert result["feasible"] and result["projected_finish"] <= result["coverage_deadline"]
    learned = [d for d in result["days"] if not d["curriculum_key"].startswith("revision:")]
    assert len(learned) == result["total_sessions"]
    assert {d["curriculum_key"].split(":")[0] for d in learned} == {
        u.key for u in CURRICULUM if u.subject in OTA
    }
    assert all(d["study_minutes"] + d["quiz_minutes"] == 120 for d in result["days"])
    assert all(d["question_count"] == 50 for d in result["days"])
    assert len({d["curriculum_key"] for d in learned}) == len(learned)
    assert all(d["date"] <= result["coverage_deadline"] for d in learned)
    assert any(d["phase"] == "revision" for d in result["days"])
    assert result == build_roadmap(today, date(2027, 4, 11), 120, OTA, set(), today)


def test_completions_only_skip_exact_saved_sessions_and_missed_days_are_not_done():
    start, today = date(2026, 10, 8), date(2026, 10, 12)
    result = build_roadmap(start, date(2027, 4, 11), 120, OTA, {"agreement:1"}, today)
    assert result["completed_sessions"] == 1
    assert result["days"][0]["date"] == today
    assert all(d["curriculum_key"] != "agreement:1" for d in result["days"])
    assert any(d["curriculum_key"] == "agreement:2" for d in result["days"])


def test_short_capacity_and_optional_maths_are_honest():
    today = date(2027, 2, 1)
    short = build_roadmap(today, date(2027, 4, 11), 30, OTA, set(), today)
    assert not short["feasible"] and short["unplaced_sessions"] > 0
    all_subjects = build_roadmap(
        date(2026, 10, 8),
        date(2027, 4, 11),
        120,
        OTA + ["elementary-mathematics"],
        set(),
        date(2026, 10, 8),
    )
    assert any(d["subject_slug"] == "elementary-mathematics" for d in all_subjects["days"])


def test_subject_rotation_remains_stable_after_completing_english():
    start = date(2026, 10, 8)
    full = build_roadmap(start, date(2027, 4, 11), 120, OTA, set(), start)
    next_day = build_roadmap(start, date(2027, 4, 11), 120, OTA, {"agreement:1"}, date(2026, 10, 9))
    assert full["days"][1]["subject_slug"] == "general-knowledge"
    assert next_day["days"][0]["subject_slug"] == "general-knowledge"
    assert next_day["days"][0]["curriculum_key"] == full["days"][1]["curriculum_key"]


def test_agreement_does_not_match_word_classes_or_shared_paper_directions():
    lesson = find_unit("agreement")
    word_classes = Question(
        prompt="Match the parts of speech: noun, verb, adverb and adjective.",
        context="Each question tests grammar, verbs and sentence agreement.",
        options=["1 2 3 4", "2 1 4 3", "3 2 1 4", "4 3 2 1"],
    )
    assert not matches_lesson(word_classes, lesson)
    determiners = Question(
        prompt="You can choose either or ____ courses.", options=["both", "few", "all", "each"]
    )
    assert not matches_lesson(determiners, lesson)
    actual = Question(
        prompt="Choose the correct verb: Neither of the proposals ____ acceptable.",
        options=["is", "are", "have", "were"],
    )
    assert matches_lesson(actual, lesson)
