# app/database.py
"""
Модуль для работы с базой данных пользователей и их токенов.
SQLite + SQLAlchemy 2.0
"""
import os
import logging
from datetime import datetime

from sqlalchemy import create_engine, Integer, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column

from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class UserToken(Base):
    """Модель хранения токенов пользователей VK."""
    __tablename__ = "user_tokens"
    
    vk_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 🔹 ИСПРАВЛЕНО: Убрали Mapped[Optional[str]], чтобы избежать бага парсинга Union в SQLAlchemy
    # nullable=True достаточно, чтобы SQLAlchemy знал, что поле может быть пустым
    device_id = mapped_column(Text, nullable=True)
    
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserToken user_id={self.vk_user_id} expires_at={self.expires_at}>"


# Путь к базе данных (в корне проекта)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "users.db")

# Создаём движок
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# Создаём фабрику сессий
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Инициализирует базу данных (создаёт таблицы, если их нет)."""
    Base.metadata.create_all(bind=engine)
    
    # 🔹 АВТОМИГРАЦИЯ: добавляем колонку device_id, если её нет (для существующих БД)
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('user_tokens')]
        
        if 'device_id' not in columns:
            with engine.connect() as conn:
                # Используем text() для сырого SQL-запроса (требование SQLAlchemy 2.0)
                conn.execute(text("ALTER TABLE user_tokens ADD COLUMN device_id TEXT"))
                conn.commit()
            logger.info("✅ Добавлена колонка device_id в существующую таблицу user_tokens")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось выполнить миграцию: {e}")
    
    logger.info(f"✅ База данных инициализирована: {DB_PATH}")


def get_session():
    """Возвращает новую сессию для работы с БД."""
    return SessionLocal()


# 🔹 ИСПРАВЛЕНО: используем str | None вместо Optional[str]
def save_user_token(vk_user_id: int, access_token: str, refresh_token: str, expires_at: datetime, device_id: str | None = None) -> bool:
    """
    Сохраняет или обновляет токен пользователя в БД.
    """
    session = get_session()
    try:
        existing = session.query(UserToken).filter_by(vk_user_id=vk_user_id).first()
        
        if existing:
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.device_id = device_id
            existing.expires_at = expires_at
            existing.updated_at = datetime.utcnow()
            logger.info(f"✅ Токен обновлён для пользователя {vk_user_id}")
        else:
            new_token = UserToken(
                vk_user_id=vk_user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                device_id=device_id,
                expires_at=expires_at
            )
            session.add(new_token)
            logger.info(f"✅ Токен сохранён для нового пользователя {vk_user_id}")
        
        session.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения токена для {vk_user_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def get_user_token(vk_user_id: int) -> UserToken | None:
    """
    Получает токен пользователя из БД.
    """
    session = get_session()
    try:
        return session.query(UserToken).filter_by(vk_user_id=vk_user_id).first()
    finally:
        session.close()


def delete_user_token(vk_user_id: int) -> bool:
    """Удаляет токен пользователя из БД."""
    session = get_session()
    try:
        token = session.query(UserToken).filter_by(vk_user_id=vk_user_id).first()
        if token:
            session.delete(token)
            session.commit()
            logger.info(f"✅ Токен удалён для пользователя {vk_user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка удаления токена для {vk_user_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()