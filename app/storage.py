from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

from app.config import settings

class Base(DeclarativeBase):
    pass

class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vk_user_id: Mapped[int] = mapped_column(Integer, index=True)
    peer_id: Mapped[int] = mapped_column(Integer, index=True)
    child_name: Mapped[str] = mapped_column(String(255), default="")
    child_age = mapped_column(Integer, nullable=True)
    event_date: Mapped[str] = mapped_column(String(32), default="")
    fact: Mapped[str] = mapped_column(Text, default="")
    post_text: Mapped[str] = mapped_column(Text, default="")
    publish_at = mapped_column(DateTime, nullable=True)
    vk_post_id = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="collecting")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    photos = relationship("DraftPhoto", back_populates="draft", cascade="all, delete-orphan")

class DraftPhoto(Base):
    __tablename__ = "draft_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), index=True)
    local_path: Mapped[str] = mapped_column(Text)
    vk_attachment = mapped_column(Text, nullable=True)

    draft = relationship("Draft", back_populates="photos")

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db() -> None:
    Base.metadata.create_all(bind=engine)

def get_session():
    return SessionLocal()
