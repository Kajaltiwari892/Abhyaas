import asyncio

from app.db.session import SessionLocal
from app.services.rag import close_rag_service, get_rag_service


async def main() -> None:
    try:
        async with SessionLocal() as db:
            count = await get_rag_service().sync_knowledge(db)
            print(f"Knowledge index ready ({count} new chunks indexed).")
    finally:
        close_rag_service()


if __name__ == "__main__":
    asyncio.run(main())
