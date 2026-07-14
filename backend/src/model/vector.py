from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ChunkBase(DeclarativeBase):
    pass


class DocumentChunk(ChunkBase):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opp_id: Mapped[int] = mapped_column(Integer, index=True)
    email_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(512), default="")
    page: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text, default="")
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
