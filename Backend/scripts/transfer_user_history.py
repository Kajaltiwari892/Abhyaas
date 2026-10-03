"""One-account, insert-only history transfer. Never exposed as an HTTP endpoint.

Export only from loopback development DBs into an ignored .vercel file. Receive
inside the backend's production environment; check is read-only, apply requires
an exact bundle SHA256. Existing live histories and credentials are never changed.
Only counts/checksums are logged. Do not commit or print the private bundle.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import lzma
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, func, insert, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models.auth import User  # noqa: E402
from app.models.papers import PaperAnswer, PaperAttempt, PaperQuestion, PreviousPaper  # noqa: E402
from app.models.practice import (  # noqa: E402
    AttemptQuestion,
    PracticeAnswer,
    PracticeAttempt,
    Question,
    Subject,
    Topic,
)
from app.models.rag import DoubtConversation, DoubtMessage  # noqa: E402

ENV_NAME = "ABHYAAS_HISTORY_TRANSFER_20261001"
MAX_BYTES = 8_000_000
MODELS = [
    PracticeAttempt,
    AttemptQuestion,
    PracticeAnswer,
    PaperAttempt,
    PaperAnswer,
    DoubtConversation,
    DoubtMessage,
]
FIELDS = {
    "practice_attempts": "id user_id subject_id topic_id status total_questions correct_answers "
    "duration_seconds time_limit_seconds current_position negative_mark_fraction "
    "started_at completed_at",
    "attempt_questions": "id attempt_id question_id position",
    "practice_answers": "id attempt_id question_id selected_index is_correct marked_for_review "
    "answered_at",
    "paper_attempts": "id paper_id user_id status total_questions scored_questions correct_answers "
    "score duration_seconds started_at completed_at",
    "paper_answers": "id attempt_id question_id selected_index is_correct "
    "marked_for_review answered_at",
    "doubt_conversations": "id user_id title created_at updated_at",
    "doubt_messages": "id conversation_id role content citations confidence "
    "pyq_result practice_result created_at",
}
PARENTS = {
    "attempt_questions": ("practice_attempts", "attempt_id"),
    "practice_answers": ("practice_attempts", "attempt_id"),
    "paper_answers": ("paper_attempts", "attempt_id"),
    "doubt_messages": ("doubt_conversations", "conversation_id"),
}
REFERENCES = {
    "subjects": (Subject, "id slug code"),
    "topics": (Topic, "id subject_id slug"),
    "questions": (Question, "id topic_id prompt context options correct_index"),
    "previous_papers": (PreviousPaper, "id subject_id year cycle"),
    "paper_questions": (PaperQuestion, "id paper_id number"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normal(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC).isoformat()
    return value


def record(row, fields):
    return {key: normal(row[key]) for key in fields.split()}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


async def rows_for(db, model, condition):
    return list((await db.execute(select(model.__table__).where(condition))).mappings())


async def export_history(db, email):
    user = (
        await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    ).scalar_one_or_none()
    require(user and user.is_active and user.is_verified, "Verified active source account required")
    tables = {}
    for model in MODELS:
        name = model.__tablename__
        if name in PARENTS:
            parent, key = PARENTS[name]
            condition = getattr(model, key).in_([r["id"] for r in tables[parent]])
        else:
            condition = model.user_id == user.id
        tables[name] = [record(row, FIELDS[name]) for row in await rows_for(db, model, condition)]
    wanted = {
        "subjects": {r["subject_id"] for r in tables["practice_attempts"]},
        "topics": {r["topic_id"] for r in tables["practice_attempts"] if r["topic_id"]},
        "questions": {
            r["question_id"]
            for name in ["attempt_questions", "practice_answers"]
            for r in tables[name]
        },
        "previous_papers": {r["paper_id"] for r in tables["paper_attempts"]},
        "paper_questions": {r["question_id"] for r in tables["paper_answers"]},
    }
    refs = {}
    for name, (model, fields) in REFERENCES.items():
        refs[name] = [
            record(row, fields) for row in await rows_for(db, model, model.id.in_(wanted[name]))
        ]
        require(len(refs[name]) == len(wanted[name]), "Missing local catalog reference: " + name)
    return {
        "version": 1,
        "email": user.email.lower(),
        "source_user_id": user.id,
        "snapshot_at": datetime.now(UTC).isoformat(),
        "tables": tables,
        "references": refs,
    }


def validate_bundle(bundle):
    require(
        set(bundle)
        == {"version", "email", "source_user_id", "snapshot_at", "tables", "references"},
        "Unexpected bundle fields",
    )
    require(bundle["version"] == 1, "Unsupported bundle version")
    require(set(bundle["tables"]) == set(FIELDS), "Unexpected history tables")
    require(set(bundle["references"]) == set(REFERENCES), "Unexpected catalog references")
    for name, fields in FIELDS.items():
        rows = bundle["tables"][name]
        require(len({r["id"] for r in rows}) == len(rows), "Duplicate source ID: " + name)
        for row in rows:
            require(set(row) == set(fields.split()), "Unexpected columns: " + name)
            if name in PARENTS:
                parent, key = PARENTS[name]
                require(
                    row[key] in {p["id"] for p in bundle["tables"][parent]},
                    "Child outside source account: " + name,
                )
            else:
                require(row["user_id"] == bundle["source_user_id"], "Mixed source accounts")
    expected_refs = {
        "subjects": {r["subject_id"] for r in bundle["tables"]["practice_attempts"]},
        "topics": {r["topic_id"] for r in bundle["tables"]["practice_attempts"] if r["topic_id"]},
        "questions": {
            r["question_id"]
            for name in ["attempt_questions", "practice_answers"]
            for r in bundle["tables"][name]
        },
        "previous_papers": {r["paper_id"] for r in bundle["tables"]["paper_attempts"]},
        "paper_questions": {r["question_id"] for r in bundle["tables"]["paper_answers"]},
    }
    for name, (_, fields) in REFERENCES.items():
        refs = bundle["references"][name]
        require(len({r["id"] for r in refs}) == len(refs), "Duplicate catalog reference")
        require({r["id"] for r in refs} == expected_refs[name], "Incomplete references: " + name)
        require(all(set(r) == set(fields.split()) for r in refs), "Unexpected reference columns")


def sql_values(model, source, target_id):
    row = dict(source)
    if "user_id" in row:
        row["user_id"] = target_id
    for col in model.__table__.columns:
        if isinstance(col.type, DateTime) and row.get(col.name) is not None:
            row[col.name] = datetime.fromisoformat(row[col.name])
    return row


async def transfer_history(db, bundle, apply=False):
    """Caller owns transaction. Any validation/insert failure rolls back everything."""
    validate_bundle(bundle)
    user = (
        await db.execute(
            select(User).where(func.lower(User.email) == bundle["email"]).with_for_update()
        )
    ).scalar_one_or_none()
    require(user and user.is_active and user.is_verified, "Verified matching live account required")
    require(user.id != bundle["source_user_id"], "Source and destination account IDs are identical")
    for name, (model, fields) in REFERENCES.items():
        refs = bundle["references"][name]
        actual = {
            r["id"]: record(r, fields)
            for r in await rows_for(db, model, model.id.in_([r["id"] for r in refs]))
        }
        for ref in refs:
            require(actual.get(ref["id"]) == ref, "Missing or changed live catalog: " + name)
    inserted, skipped, pending = {}, {}, {}
    for model in MODELS:
        name = model.__tablename__
        source = bundle["tables"][name]
        existing = {
            r["id"]: r for r in await rows_for(db, model, model.id.in_([r["id"] for r in source]))
        }
        pending[name] = []
        for row in source:
            current = existing.get(row["id"])
            if name in PARENTS:
                parent, key = PARENTS[name]
                if current:
                    require(current[key] == row[key], "Live child ID collision: " + name)
                # Never add/replace answers or messages in any existing live history.
                if row[key] not in {r["id"] for r in pending[parent]}:
                    continue
                require(current is None, "Unexpected existing child of new parent: " + name)
            elif current:
                require(current["user_id"] == user.id, "Live parent ID belongs to another account")
                continue
            pending[name].append(sql_values(model, row, user.id))
        inserted[name] = len(pending[name])
        skipped[name] = len(source) - inserted[name]
    before = {}
    for model in [PracticeAttempt, PaperAttempt, DoubtConversation]:
        before[model.__tablename__] = (
            await db.execute(
                select(func.count()).select_from(model).where(model.user_id == user.id)
            )
        ).scalar_one()
    if apply:
        for model in MODELS:
            data = pending[model.__tablename__]
            if data:
                await db.execute(insert(model.__table__), data)
        # Compare every field we inserted, including answers, durations and chat payloads.
        for model in MODELS:
            name = model.__tablename__
            data = pending[name]
            actual = {
                r["id"]: record(r, FIELDS[name])
                for r in await rows_for(db, model, model.id.in_([r["id"] for r in data]))
            }
            require(
                all(actual.get(r["id"]) == record(r, FIELDS[name]) for r in data),
                "Post-insert verification failed: " + name,
            )
    return {
        "mode": "apply" if apply else "check",
        "sha256": fingerprint(bundle),
        "matching_verified_account": True,
        "existing_live": before,
        "inserted" if apply else "would_insert": inserted,
        "preserved_or_skipped": skipped,
    }


def unpack(encoded):
    compressed = base64.b64decode(encoded.strip(), validate=True)
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
    raw = decoder.decompress(compressed, MAX_BYTES + 1)
    require(
        len(raw) <= MAX_BYTES and decoder.eof and not decoder.unused_data,
        f"Invalid transfer: encoded_bytes={len(encoded.strip())}, "
        f"decoded_bytes={len(raw)}, complete={decoder.eof}, trailing={len(decoder.unused_data)}",
    )
    return json.loads(raw)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--email", required=True)
    export.add_argument("--output", type=Path, required=True)
    receive = sub.add_parser("receive")
    receive.add_argument("--sha256", required=True)
    receive.add_argument("--parts", type=int, default=1)
    receive.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from app.db.session import SessionLocal, engine

    try:
        if args.command == "export":
            require(
                engine.url.host in {"localhost", "127.0.0.1", "::1"},
                "Export requires the local development DB",
            )
            destination = args.output.resolve()
            require(
                destination.is_relative_to((ROOT / ".vercel").resolve()),
                "Private exports must stay under ignored Backend/.vercel",
            )
            require(not destination.exists(), "Refusing to overwrite an existing export")
            async with SessionLocal() as db, db.begin():
                await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                bundle = await export_history(db, args.email)
            validate_bundle(bundle)
            encoded = base64.b64encode(lzma.compress(canonical(bundle), preset=9)).decode("ascii")
            require(len(encoded) <= 48_000, "Bundle too large for the private environment channel")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(encoded, encoding="ascii")
            print(
                json.dumps(
                    {
                        "exported": {k: len(v) for k, v in bundle["tables"].items()},
                        "encoded_bytes": len(encoded),
                        "sha256": fingerprint(bundle),
                    }
                )
            )
        else:
            require(os.environ.get("VERCEL_ENV") == "production", "Production job required")
            require(
                engine.url.host not in {None, "localhost", "127.0.0.1", "::1"},
                "Remote destination DB required",
            )
            require(1 <= args.parts <= 20, "Invalid private transfer part count")
            bundle = unpack(
                "".join(os.environ[f"{ENV_NAME}_{i}"] for i in range(1, args.parts + 1))
            )
            require(fingerprint(bundle) == args.sha256, "Bundle checksum mismatch")
            async with SessionLocal() as db, db.begin():
                await db.execute(text("SET LOCAL lock_timeout = '10s'"))
                await db.execute(text("SET LOCAL statement_timeout = '90s'"))
                result = await transfer_history(db, bundle, apply=args.apply)
            # Transaction exited successfully before announcing success.
            print("HISTORY_TRANSFER " + json.dumps(result))
            # Read through the same dashboard function used by the live app, in a
            # fresh session. Log counts only, never scores, titles or messages.
            from app.api.v1.progress import progress_dashboard

            async with SessionLocal() as db:
                user = (
                    await db.execute(select(User).where(func.lower(User.email) == bundle["email"]))
                ).scalar_one()
                dashboard = await progress_dashboard(user, db)
                conversation_ids = select(DoubtConversation.id).where(
                    DoubtConversation.user_id == user.id
                )
                message_count = (
                    await db.execute(
                        select(func.count())
                        .select_from(DoubtMessage)
                        .where(DoubtMessage.conversation_id.in_(conversation_ids))
                    )
                ).scalar_one()
                print(
                    "HISTORY_DASHBOARD_CHECK "
                    + json.dumps(
                        {
                            "completed_sets": dashboard.completed_sets,
                            "dashboard_history_items": len(dashboard.history),
                            "chat_messages": message_count,
                        }
                    )
                )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        # SQLAlchemy exceptions can embed private query parameters. Never log them.
        print(
            "History transfer stopped safely: "
            + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__),
            file=sys.stderr,
        )
        sys.exit(1)
