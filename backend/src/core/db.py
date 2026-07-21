from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings
from model.relational import Base
from model.vector import ChunkBase

settings = get_settings()

rel_engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)
vec_engine = create_async_engine(settings.pgvector_url, pool_pre_ping=True)

RelSessionLocal = async_sessionmaker(rel_engine, expire_on_commit=False, class_=AsyncSession)
VecSessionLocal = async_sessionmaker(vec_engine, expire_on_commit=False, class_=AsyncSession)


async def get_rel_db() -> AsyncGenerator[AsyncSession, None]:
    async with RelSessionLocal() as session:
        yield session


async def get_vec_db() -> AsyncGenerator[AsyncSession, None]:
    async with VecSessionLocal() as session:
        yield session


async def init_databases() -> None:
    async with rel_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns on existing volumes (create_all does not alter tables)
        for stmt in (
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS project_type VARCHAR(64)",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS bid_quality VARCHAR(64)",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS bid_quality_confidence DOUBLE PRECISION",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS bid_quality_rationale TEXT",
            "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS project_type VARCHAR(64)",
            "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS bid_quality VARCHAR(64)",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS body_html TEXT",
        ):
            await conn.execute(text(stmt))

    async with vec_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(ChunkBase.metadata.create_all)
