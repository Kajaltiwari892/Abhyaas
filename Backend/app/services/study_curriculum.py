"""A dated, time-budgeted CDS roadmap, not a random list of bank topics.

The detailed units are Abhyaas's breakdown of the broad UPSC syllabus, not an
official chapter list. Estimates are planning aids, never proof of mastery.
"""

import calendar
import math
from collections import deque
from dataclasses import dataclass
from datetime import date, timedelta

EXAM_DATE = date(2027, 4, 11)
EXAM_SOURCE = "https://www.upsc.gov.in/sites/default/files/Calendar-Year-2027-Engl-200526.pdf"
SYLLABUS_SOURCE = "https://upsc.gov.in/sites/default/files/Notifi-CDSE-I-2025-Engl-11122024.pdf"
SUBJECT_NAMES = {
    "english": "English",
    "general-knowledge": "General Knowledge",
    "elementary-mathematics": "Mathematics",
}


@dataclass(frozen=True)
class Unit:
    key: str
    subject: str
    topic: str
    title: str
    minutes: int
    points: tuple[str, ...]
    terms: tuple[str, ...]


def unit(key, subject, topic, title, minutes, points, terms):
    return Unit(
        key, subject, topic, title, minutes, tuple(points.split(" | ")), tuple(terms.split("|"))
    )


CURRICULUM = [
    unit(
        "agreement",
        "english",
        "grammar",
        "Subject–verb agreement",
        140,
        (
            "Subject and verb agreement | Either/neither, collective nouns and "
            "quantifiers | CDS error-spotting practice"
        ),
        "agreement|neither|either|each",
    ),
    unit(
        "tenses",
        "english",
        "grammar",
        "Tenses and verb forms",
        140,
        "Present, past and perfect forms | Sequence of tenses | Participles and infinitives",
        "tense|participle|infinitive|past perfect|present perfect",
    ),
    unit(
        "articles",
        "english",
        "grammar",
        "Articles, prepositions and determiners",
        140,
        "Articles and zero article | Contextual prepositions | Determiners and conjunctions",
        "article|preposition|determiner|conjunction",
    ),
    unit(
        "sentence-grammar",
        "english",
        "error-spotting",
        "Modifiers, conditionals and parallelism",
        140,
        (
            "Misplaced modifiers | Conditional and inverted sentences | "
            "Parallel structures and error spotting"
        ),
        "modifier|conditional|inversion|parallel",
    ),
    unit(
        "voice",
        "english",
        "grammar",
        "Voice and reported speech",
        70,
        "Active and passive voice | Direct and indirect speech | Correct tense and pronoun changes",
        "passive|active|speech|narration",
    ),
    unit(
        "word-classes",
        "english",
        "grammar",
        "Word classes and parts of speech",
        70,
        (
            "Nouns, pronouns, verbs and modifiers | Identify word classes in context | "
            "CDS word-class matching"
        ),
        "parts of speech|word class|noun|pronoun|verb|adverb|adjective|interjection",
    ),
    unit(
        "errors",
        "english",
        "error-spotting",
        "Error spotting and sentence improvement",
        140,
        (
            "Apply grammar to complete sentences | Compare plausible "
            "alternatives | Practise identifying the exact error"
        ),
        "error|improvement|grammatical",
    ),
    unit(
        "cloze",
        "english",
        "grammar",
        "Fill in the blanks and cloze tests",
        140,
        "Contextual word selection | Collocations | Paragraph-level cloze reasoning",
        "blank|cloze|complete",
    ),
    unit(
        "synonyms",
        "english",
        "vocabulary",
        "Synonyms and contextual vocabulary",
        140,
        "Word meaning in context | Distinguish near-synonyms | Review difficult vocabulary",
        "synonym|meaning|vocabulary",
    ),
    unit(
        "antonyms",
        "english",
        "vocabulary",
        "Antonyms and word usage",
        140,
        "Contextual opposites | Commonly confused words | Appropriate word usage",
        "antonym|opposite|word",
    ),
    unit(
        "idioms",
        "english",
        "idioms",
        "Idioms, phrases and one-word substitutions",
        140,
        "Idiomatic meanings | Phrasal verbs | One-word substitutions",
        "idiom|phrase|substitution",
    ),
    unit(
        "ordering",
        "english",
        "sentence-ordering",
        "Sentence ordering and relationships",
        140,
        "Ordering sentence parts | Paragraph sequencing | Logical sentence relationships",
        "sequence|ordering|sentence|relationship",
    ),
    unit(
        "reading",
        "english",
        "comprehension",
        "Reading comprehension",
        210,
        (
            "Main idea and author's tone | Inference versus stated facts | "
            "Vocabulary from a complete passage"
        ),
        "passage|comprehension|author|inference",
    ),
    unit(
        "ancient",
        "general-knowledge",
        "history",
        "Ancient India",
        140,
        "Indus Valley and Vedic age | Buddhism and Jainism | Mauryas, Guptas and early kingdoms",
        "indus|vedic|buddh|jain|maurya|gupta|ancient",
    ),
    unit(
        "medieval",
        "general-knowledge",
        "history",
        "Medieval India",
        140,
        "Delhi Sultanate and Mughals | Bhakti and Sufi movements | Regional kingdoms",
        "sultan|mughal|bhakti|sufi|medieval",
    ),
    unit(
        "colonial",
        "general-knowledge",
        "history",
        "Colonial rule and the revolt of 1857",
        140,
        "Company expansion | Land revenue and social reform | Revolt of 1857",
        "company|british|1857|revenue|colonial",
    ),
    unit(
        "freedom",
        "general-knowledge",
        "history",
        "India's freedom movement",
        210,
        (
            "Congress, nationalism and reform | Gandhian movements | "
            "Independence and important personalities"
        ),
        "gandhi|congress|national|independence|movement",
    ),
    unit(
        "culture",
        "general-knowledge",
        "history",
        "Indian art and culture",
        70,
        (
            "Architecture and monuments | Literature and cultural traditions | "
            "Match places, people and periods"
        ),
        "temple|art|architecture|literature|culture",
    ),
    unit(
        "earth",
        "general-knowledge",
        "geography",
        "Earth's interior and landforms",
        140,
        (
            "Earth layers, rocks and minerals | Plate tectonics, earthquakes "
            "and volcanoes | Weathering and landforms"
        ),
        (
            "earth's interior|earth’s interior|crust|mantle|core|rock|volcan|tectonic|"
            "earthquake|landform|weathering"
        ),
    ),
    unit(
        "climate",
        "general-knowledge",
        "geography",
        "Atmosphere, weather and climate",
        140,
        "Pressure, winds and rainfall | Climatic regions | Indian monsoon and weather systems",
        "climate|weather|atmosphere|wind|monsoon|rain",
    ),
    unit(
        "india-geography",
        "general-knowledge",
        "geography",
        "Indian physical and economic geography",
        210,
        "Physiography, rivers and soils | Agriculture and resources | Population and transport",
        "india|river|soil|agriculture|resource|population",
    ),
    unit(
        "world-geography",
        "general-knowledge",
        "geography",
        "Oceans and world geography",
        140,
        "Oceans and currents | Continents and important locations | Map-based revision",
        "ocean|current|continent|latitude|longitude",
    ),
    unit(
        "environment",
        "general-knowledge",
        "geography",
        "Environment and ecology",
        140,
        "Ecosystems and biodiversity | Pollution and conservation | Climate-change fundamentals",
        "ecosystem|environment|biodiversity|pollution|conservation",
    ),
    unit(
        "constitution",
        "general-knowledge",
        "polity",
        "Constitution, rights and duties",
        140,
        (
            "Preamble and constitutional features | Fundamental rights and "
            "duties | Directive principles and amendments"
        ),
        "constitution|right|duties|preamble|amendment",
    ),
    unit(
        "government",
        "general-knowledge",
        "polity",
        "Parliament, executive and judiciary",
        210,
        (
            "Union and state institutions | Legislative procedure and "
            "elections | Judiciary and local government"
        ),
        "parliament|president|court|judiciary|election|government",
    ),
    unit(
        "economy",
        "general-knowledge",
        "economics",
        "Indian economy and development",
        140,
        (
            "National income and sectors | Planning, employment and "
            "development | Economic institutions"
        ),
        "economy|income|development|employment|sector",
    ),
    unit(
        "finance",
        "general-knowledge",
        "economics",
        "Money, banking and public finance",
        140,
        "Money, inflation and banking | Budget and taxation | External trade fundamentals",
        "money|bank|inflation|budget|tax|trade",
    ),
    unit(
        "mechanics",
        "general-knowledge",
        "general-science",
        "Physics: motion, work and heat",
        140,
        (
            "Motion, force, work and energy | Heat and thermodynamics basics | "
            "Everyday applications and units"
        ),
        "force|motion|energy|heat|temperature|work",
    ),
    unit(
        "light-electricity",
        "general-knowledge",
        "general-science",
        "Physics: light, sound and electricity",
        140,
        "Optics and sound | Electricity and magnetism | Everyday scientific observation",
        "light|sound|electric|magnet|lens|mirror",
    ),
    unit(
        "chemistry",
        "general-knowledge",
        "general-science",
        "Chemistry in everyday life",
        210,
        (
            "Atoms, elements and reactions | Acids, bases and salts | Metals, "
            "carbon and everyday chemicals"
        ),
        "chemical|acid|base|salt|metal|carbon|atom",
    ),
    unit(
        "biology",
        "general-knowledge",
        "general-science",
        "Biology, health and the human body",
        210,
        (
            "Cells and life processes | Human systems and nutrition | "
            "Diseases, immunity and plant biology"
        ),
        "cell|human|disease|nutrition|plant|blood|vitamin",
    ),
    unit(
        "defence-awareness",
        "general-knowledge",
        "mixed-gk",
        "Defence, organisations and general awareness",
        70,
        (
            "Defence institutions and basic awareness | International "
            "organisations | Important general-awareness themes"
        ),
        "defence|military|organisation|united nations|army|navy",
    ),
    unit(
        "numbers",
        "elementary-mathematics",
        "arithmetic",
        "Numbers and elementary number theory",
        140,
        (
            "Integers, rational numbers and fractions | HCF, LCM and "
            "divisibility | Roots and logarithms"
        ),
        "number|divisib|hcf|lcm|root|log",
    ),
    unit(
        "ratios",
        "elementary-mathematics",
        "arithmetic",
        "Ratio, percentage and commercial arithmetic",
        140,
        "Ratio and proportion | Percentages, profit and loss | Simple and compound interest",
        "ratio|percent|profit|loss|interest",
    ),
    unit(
        "work-speed",
        "elementary-mathematics",
        "arithmetic",
        "Time, work, speed and distance",
        140,
        "Work-rate problems | Relative speed | Time and distance applications",
        "speed|distance|work|time",
    ),
    unit(
        "algebra",
        "elementary-mathematics",
        "algebra",
        "Algebra and equations",
        210,
        "Identities and factorisation | Linear and quadratic equations | Sets and inequalities",
        "equation|polynomial|factor|identity|set",
    ),
    unit(
        "geometry",
        "elementary-mathematics",
        "geometry",
        "Plane geometry",
        210,
        "Lines, angles and triangles | Circles and quadrilaterals | Similarity and geometric proof",
        "triangle|circle|angle|quadrilateral|geometry",
    ),
    unit(
        "trigonometry",
        "elementary-mathematics",
        "trigonometry",
        "Trigonometry and heights and distances",
        140,
        "Ratios and standard angles | Identities | Heights and distances",
        "sin|cos|tan|height|trigon",
    ),
    unit(
        "mensuration",
        "elementary-mathematics",
        "mensuration",
        "Mensuration",
        140,
        "Plane areas and perimeter | Surface areas and volumes | Composite solids",
        "area|volume|surface|cone|cylinder|sphere",
    ),
    unit(
        "statistics",
        "elementary-mathematics",
        "arithmetic",
        "Statistics and data interpretation",
        70,
        "Tables and graphs | Mean, median and mode | Data-based calculations",
        "mean|median|mode|graph|table",
    ),
]


def coverage_deadline(exam: date) -> date:
    month_index = exam.year * 12 + exam.month - 3
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(exam.day, calendar.monthrange(year, month)[1]))


def find_unit(key: str | None) -> Unit | None:
    parts = (key or "").split(":")
    name = parts[1] if len(parts) > 1 and parts[0] == "revision" else parts[0]
    return next((u for u in CURRICULUM if u.key == name), None)


def build_roadmap(
    start: date, exam: date, minutes: int, subjects: list[str], completed: set[str], today: date
) -> dict:
    deadline = coverage_deadline(exam)
    units = [u for u in CURRICULUM if u.subject in subjects]
    queues = {}
    total_sessions = 0
    for subject in subjects:
        quiz_minutes = 60 if subject == "elementary-mathematics" else 50
        study_minutes = max(10, minutes - quiz_minutes)
        sessions = []
        for u in units:
            if u.subject != subject:
                continue
            count = math.ceil(u.minutes / study_minutes)
            for part in range(1, count + 1):
                key = f"{u.key}:{part}"
                total_sessions += 1
                sessions.append(
                    {
                        "curriculum_key": key,
                        "subject_slug": subject,
                        "subject_name": SUBJECT_NAMES[subject],
                        "topic_slug": u.topic,
                        "topic_name": u.title,
                        "focus_points": list(u.points),
                        "session": part,
                        "sessions": count,
                        "study_minutes": study_minutes,
                        "quiz_minutes": quiz_minutes,
                        "question_count": 50,
                    }
                )
        queues[subject] = deque(sessions)
    ordered = []
    while any(queues.values()):
        for subject in subjects:
            if queues[subject]:
                ordered.append(queues[subject].popleft())
    # Filter only AFTER building the complete interleaved sequence. Otherwise
    # deleting English's first session would put English first again every day.
    ordered = [item for item in ordered if item["curriculum_key"] not in completed]
    days, index, finish = [], 0, today - timedelta(days=1)
    first = max(start, today)
    for offset in range(max(0, (exam - first).days)):
        day = first + timedelta(days=offset)
        # Weekly reserved days keep catch-up from silently replacing all new units.
        buffer = (day - start).days % 7 == 6
        if index < len(ordered) and not buffer:
            item = dict(ordered[index])
            index += 1
            finish = day
            phase = "learn" if day <= deadline else "catch-up"
        else:
            subject = subjects[offset % len(subjects)]
            topic_units = [u for u in units if u.subject == subject]
            chosen = topic_units[(offset // 7) % len(topic_units)]
            item = {
                "curriculum_key": f"revision:{chosen.key}:{day.isoformat()}",
                "subject_slug": subject,
                "subject_name": SUBJECT_NAMES[subject],
                "topic_slug": chosen.topic,
                "topic_name": f"Revision · {chosen.title}",
                "focus_points": list(chosen.points),
                "session": 1,
                "sessions": 1,
                "study_minutes": max(
                    10, minutes - (60 if subject == "elementary-mathematics" else 50)
                ),
                "quiz_minutes": 60 if subject == "elementary-mathematics" else 50,
                "question_count": 50,
            }
            phase = "revision"
        days.append({"date": day, "phase": phase, **item})
    unplaced = len(ordered) - index
    feasible = (
        not unplaced
        and finish <= deadline
        and minutes >= (70 if "elementary-mathematics" in subjects else 60)
    )
    return {
        "exam_date": exam,
        "coverage_deadline": deadline,
        "start_date": start,
        "projected_finish": finish if not unplaced else None,
        "feasible": feasible,
        "total_sessions": total_sessions,
        "completed_sessions": total_sessions - len(ordered),
        "unplaced_sessions": unplaced,
        "daily_minutes": minutes,
        "units": [
            {
                "key": u.key,
                "subject_name": SUBJECT_NAMES[u.subject],
                "title": u.title,
                "focus_points": list(u.points),
            }
            for u in units
        ],
        "days": days,
        "syllabus_source": SYLLABUS_SOURCE,
        "exam_source": EXAM_SOURCE if exam == EXAM_DATE else None,
        "current_affairs_note": (
            "Read current affairs daily from a trusted newspaper. Use the "
            "final revision period to update recent events."
        ),
    }
