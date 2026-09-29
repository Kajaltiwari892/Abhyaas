"""add RAG knowledge base and doubt conversations

Revision ID: 20260921_12
Revises: 20260917_11
Create Date: 2026-09-21
"""

# ruff: noqa: E501 -- seed passages remain readable as source material.

import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260921_12"
down_revision: str | None = "20260917_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("867ad8b3-bdea-4ddc-b686-603aa2219b4c")


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


SOURCES = [
    {
        "key": "constitution-fundamental-rights",
        "title": "The Constitution of India",
        "publisher": "Legislative Department, Ministry of Law and Justice",
        "source_url": "https://www.legislative.gov.in/static/uploads/2025/08/cb1b190ea633a1746368ed1fac35fb30.pdf",
        "source_type": "official_publication",
        "subject": "general-knowledge",
        "edition": "Official English edition, 2024",
        "chunks": [
            (
                "Part III — General (Articles 12–13)",
                "Part III contains Fundamental Rights. Article 12 explains what 'the State' means for this Part, including Union and State governments and legislatures and authorities within India or under Government of India control. Article 13 makes laws void to the extent that they conflict with Fundamental Rights and restricts the State from making laws that take away or abridge those rights.",
            ),
            (
                "Right to Equality (Articles 14–18)",
                "The Right to Equality covers equality before law and equal protection of laws; prohibition of discrimination on specified grounds; equality of opportunity in public employment; abolition of untouchability; and abolition of titles other than military or academic distinctions. Reasonable classification can be valid when it has an intelligible basis and a rational connection to the law's objective.",
            ),
            (
                "Right to Freedom (Articles 19–22)",
                "Articles 19 to 22 protect important freedoms and personal safeguards. Article 19 gives citizens six freedoms, including speech and expression, peaceful assembly, association, movement, residence, and profession, subject to constitutionally permitted reasonable restrictions. Articles 20 and 21 protect accused persons and life and personal liberty. Article 22 provides safeguards concerning arrest and detention, with stated exceptions.",
            ),
            (
                "Right against Exploitation (Articles 23–24)",
                "Articles 23 and 24 form the Right against Exploitation. Article 23 prohibits trafficking in human beings, begar, and similar forced labour, while allowing compulsory service for public purposes without prohibited discrimination. Article 24 prohibits employing children below fourteen years in factories, mines, or other hazardous employment.",
            ),
            (
                "Freedom of Religion (Articles 25–28)",
                "Articles 25 to 28 protect freedom of conscience and religion, subject to public order, morality, health, and other Fundamental Rights. They address the profession, practice and propagation of religion, management of religious affairs, freedom from certain religion-specific taxes, and religious instruction in specified educational institutions.",
            ),
            (
                "Cultural, Educational and Constitutional Remedies (Articles 29–32)",
                "Articles 29 and 30 protect cultural and educational interests, including the right of minorities based on religion or language to establish and administer educational institutions. Article 32 guarantees the right to approach the Supreme Court to enforce Fundamental Rights and empowers it to issue constitutional writs such as habeas corpus, mandamus, prohibition, quo warranto, and certiorari.",
            ),
        ],
    },
    {
        "key": "wmo-weather-climate",
        "title": "Weather",
        "publisher": "World Meteorological Organization",
        "source_url": "https://wmo.int/themes/weather",
        "source_type": "official_webpage",
        "subject": "general-knowledge",
        "edition": "Accessed September 2026",
        "chunks": [
            (
                "Weather and climate",
                "Weather describes atmospheric conditions at a particular time and place. Climate describes typical or average conditions and their variability over a much longer period. The World Meteorological Organization uses 30-year periods for standard climatological normals. A single hot, cold, wet, or dry day is therefore weather and does not by itself establish a climate trend.",
            ),
            (
                "Weather observations and forecasts",
                "Common weather observations include temperature, atmospheric pressure, wind, humidity, cloud, precipitation, and visibility. Forecasting combines measurements from ground stations, ships, buoys, aircraft, radar, and satellites with numerical models. Forecast skill generally decreases as the forecast range grows because small uncertainties in the atmosphere amplify over time.",
            ),
        ],
    },
    {
        "key": "abhyaas-time-work",
        "title": "CDS Quantitative Aptitude Foundation Notes",
        "publisher": "Abhyaas Editorial Team",
        "source_url": None,
        "source_type": "curated_notes",
        "subject": "elementary-mathematics",
        "edition": "2026.1",
        "chunks": [
            (
                "Time and work — rates",
                "Treat the whole job as 1 unit. If A completes it in x days, A's daily work rate is 1/x. When people work together, add their rates. The completion time is the reciprocal of the combined rate. For example, rates 1/12 and 1/18 add to 5/36, so the job takes 36/5 days. Use an LCM-sized imaginary job when it makes the arithmetic easier.",
            ),
            (
                "Efficiency and workforce",
                "For the same amount of work, efficiency and time are inversely proportional: if A is twice as efficient as B, A takes half as long. With constant efficiency, work is proportional to workers multiplied by days multiplied by hours per day. Equate the products for two arrangements, while adjusting for any stated change in individual efficiency.",
            ),
            (
                "Pipes, leaks and changing teams",
                "Solve pipes and cisterns as signed work rates: an inlet is positive and an outlet or leak is negative. For a changing team, calculate the fraction completed in each stage, subtract it from 1, and use the new combined rate for the remaining work. Never add times directly unless the rates are equal and the problem specifically supports it.",
            ),
        ],
    },
    {
        "key": "abhyaas-english-foundation",
        "title": "CDS English Foundation Notes",
        "publisher": "Abhyaas Editorial Team",
        "source_url": None,
        "source_type": "curated_notes",
        "subject": "english",
        "edition": "2026.1",
        "chunks": [
            (
                "Subject–verb agreement",
                "A finite verb normally agrees with the grammatical subject, not with a nearby noun inside a phrase. Singular indefinite pronouns such as each, either, neither, everyone, and anybody usually take singular verbs. With 'either...or' and 'neither...nor', agreement generally follows the subject nearer the verb. Collective nouns may be singular for a unit and plural when members act separately, depending on meaning and usage.",
            ),
            (
                "Vocabulary in context",
                "Choose a synonym or antonym only after reading the whole sentence. First decide the word's part of speech and the attitude or tone of the passage. Eliminate choices with the wrong grammatical role, intensity, or connotation. For idioms, use the established figurative meaning rather than interpreting each word literally.",
            ),
        ],
    },
]


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("publisher", sa.String(length=180), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=80), nullable=False),
        sa.Column("edition", sa.String(length=120), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum"),
    )
    op.create_index("ix_knowledge_documents_checksum", "knowledge_documents", ["checksum"])
    op.create_index("ix_knowledge_documents_is_active", "knowledge_documents", ["is_active"])
    op.create_index("ix_knowledge_documents_subject", "knowledge_documents", ["subject"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chapter", sa.String(length=240), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum"),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index("ix_knowledge_chunks_checksum", "knowledge_chunks", ["checksum"])
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])

    op.create_table(
        "doubt_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doubt_conversations_user_id", "doubt_conversations", ["user_id"])

    op.create_table(
        "doubt_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["doubt_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doubt_messages_conversation_id", "doubt_messages", ["conversation_id"])
    op.create_index("ix_doubt_messages_created_at", "doubt_messages", ["created_at"])
    op.create_index("ix_doubt_messages_role", "doubt_messages", ["role"])

    document_table = sa.table(
        "knowledge_documents",
        *(sa.column(name) for name in (
            "id", "title", "publisher", "source_url", "source_type", "subject", "edition",
            "checksum", "is_active", "created_at",
        )),
    )
    chunk_table = sa.table(
        "knowledge_chunks",
        *(sa.column(name) for name in (
            "id", "document_id", "chunk_index", "chapter", "page_start", "page_end", "content",
            "checksum", "created_at",
        )),
    )
    created_at = datetime(2026, 9, 21, tzinfo=UTC)
    for source in SOURCES:
        document_id = stable_id(f"rag-document:{source['key']}")
        full_text = "\n".join(content for _, content in source["chunks"])
        op.bulk_insert(document_table, [{
            "id": document_id,
            "title": source["title"],
            "publisher": source["publisher"],
            "source_url": source["source_url"],
            "source_type": source["source_type"],
            "subject": source["subject"],
            "edition": source["edition"],
            "checksum": digest(full_text),
            "is_active": True,
            "created_at": created_at,
        }])
        op.bulk_insert(chunk_table, [
            {
                "id": stable_id(f"rag-chunk:{source['key']}:{index}"),
                "document_id": document_id,
                "chunk_index": index,
                "chapter": chapter,
                "page_start": None,
                "page_end": None,
                "content": content,
                "checksum": digest(f"{document_id}:{index}:{content}"),
                "created_at": created_at,
            }
            for index, (chapter, content) in enumerate(source["chunks"])
        ])


def downgrade() -> None:
    op.drop_table("doubt_messages")
    op.drop_table("doubt_conversations")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
