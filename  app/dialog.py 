from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import uuid

from app.storage import get_session, Draft, DraftPhoto
from app.llm_service import generate_post
from app.vk_keyboard import moderation_keyboard, back_keyboard
from app.config import settings

@dataclass
class UserState:
    step: str = "start"
    draft_id: int | None = None

class DialogManager:
    def __init__(self, vk_client, chat_with_llm):
        self.vk = vk_client
        self.chat_with_llm = chat_with_llm
        self.states: dict[int, UserState] = {}

    def get_state(self, peer_id: int) -> UserState:
        return self.states.setdefault(peer_id, UserState())

    def is_allowed(self, user_id: int) -> bool:
        return bool(settings.admin_user_ids) and user_id in settings.admin_user_ids

    def handle_public_user(self, peer_id: int, user_id: int, text: str) -> tuple[str, str | None]:
        return "Спасибо, ваше сообщение принято. Оператор ответит вам лично.", None

    def start(self, peer_id: int, vk_user_id: int) -> tuple[str, str | None]:
        if not self.is_allowed(vk_user_id):
            return self.handle_public_user(peer_id, vk_user_id, "/start")

        session = get_session()
        draft = Draft(vk_user_id=vk_user_id, peer_id=peer_id, status="await_photos")
        session.add(draft)
        session.commit()
        session.refresh(draft)
        self.get_state(peer_id).draft_id = draft.id
        self.get_state(peer_id).step = "await_photos"
        session.close()
        return "Пришлите несколько фото с праздника.", None

    def save_incoming_photo(self, url: str) -> str:
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.jpg"
        path = str(Path(settings.upload_dir) / filename)
        self.vk.download_photo(url, path)
        return path

    def add_photo_paths(self, peer_id: int, user_id: int, paths: list[str]) -> tuple[str, str | None]:
        if not self.is_allowed(user_id):
            return self.handle_public_user(peer_id, user_id, "photo")

        state = self.get_state(peer_id)
        if state.draft_id is None:
            return "Сначала нажмите /start.", None

        session = get_session()
        draft = session.get(Draft, state.draft_id)
        if not draft:
            session.close()
            return "Черновик не найден. Начните заново.", None

        for p in paths:
            session.add(DraftPhoto(draft_id=draft.id, local_path=p))
        draft.status = "await_name"
        session.commit()
        session.close()
        state.step = "await_name"
        return "Фото приняты. Теперь отправьте имя ребенка.", None

    def render_draft(self, draft: Draft) -> str:
        photos_count = len(draft.photos)
        return (
            f"Черновик поста:\n\n{draft.post_text}\n\n"
            f"Имя: {draft.child_name}\n"
            f"Возраст: {draft.child_age}\n"
            f"Дата мероприятия: {draft.event_date}\n"
            f"Фото: {photos_count}\n"
        )

    def handle_text(self, peer_id: int, user_id: int, text: str) -> tuple[str, str | None]:
        if not self.is_allowed(user_id):
            return self.handle_public_user(peer_id, user_id, text)

        state = self.get_state(peer_id)
        if state.draft_id is None:
            return "Сначала нажмите /start.", None

        session = get_session()
        draft = session.get(Draft, state.draft_id)
        if not draft:
            session.close()
            return "Черновик не найден.", None

        if state.step == "await_name":
            draft.child_name = text
            draft.status = "await_age"
            state.step = "await_age"
            session.commit()
            session.close()
            return "Теперь отправьте возраст ребенка.", None

        if state.step == "await_age":
            try:
                draft.child_age = int(text)
            except ValueError:
                session.close()
                return "Возраст должен быть числом.", None
            draft.status = "await_event_date"
            state.step = "await_event_date"
            session.commit()
            session.close()
            return "Теперь отправьте дату проведения мероприятия.", None

        if state.step == "await_event_date":
            draft.event_date = text
            draft.status = "await_fact"
            state.step = "await_fact"
            session.commit()
            session.close()
            return "Теперь отправьте интересный факт.", None

        if state.step == "await_fact":
            draft.fact = text
            photos_count = len(draft.photos)
            draft.post_text = generate_post(
                draft.child_name,
                draft.child_age or 0,
                draft.event_date,
                draft.fact,
                photos_count,
                self.chat_with_llm,
            )
            draft.status = "await_review"
            state.step = "await_review"
            session.commit()
            out = self.render_draft(draft)
            session.close()
            return out, moderation_keyboard()

        if state.step == "await_edit":
            draft.post_text = text
            draft.status = "await_publish_date"
            state.step = "await_publish_date"
            session.commit()
            session.close()
            return "Текст обновлен. Теперь отправьте дату и время публикации в формате YYYY-MM-DD HH:MM.", None

        if state.step == "await_publish_date":
            try:
                publish_dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            except ValueError:
                session.close()
                return "Неверный формат даты. Используйте YYYY-MM-DD HH:MM.", None

            photo_paths = [p.local_path for p in draft.photos]
            attachments = self.vk.upload_wall_photos(photo_paths) if photo_paths else []
            result = self.vk.schedule_wall_post(
                message=draft.post_text,
                attachments=attachments,
                publish_date=int(publish_dt.timestamp()),
            )

            draft.publish_at = publish_dt
            draft.vk_post_id = result.get("post_id")
            draft.status = "scheduled"
            session.commit()
            session.close()
            state.step = "scheduled"
            return f"Пост запланирован в VK. ID записи: {result.get('post_id')}", None

        session.close()
        return "Команда не распознана.", None

    def handle_button(self, peer_id: int, user_id: int, payload: dict) -> tuple[str, str | None]:
        if not self.is_allowed(user_id):
            return self.handle_public_user(peer_id, user_id, "button")

        action = payload.get("action")
        state = self.get_state(peer_id)

        session = get_session()
        draft = session.get(Draft, state.draft_id) if state.draft_id else None
        if not draft:
            session.close()
            return "Черновик не найден.", None

        if action == "confirm":
            state.step = "await_publish_date"
            draft.status = "await_publish_date"
            session.commit()
            session.close()
            return "Отправьте дату и время публикации в формате YYYY-MM-DD HH:MM.", back_keyboard()

        if action == "edit":
            state.step = "await_edit"
            draft.status = "editing"
            session.commit()
            session.close()
            return "Отправьте новый вариант текста.", back_keyboard()

        if action == "publish_date":
            state.step = "await_publish_date"
            draft.status = "await_publish_date"
            session.commit()
            session.close()
            return "Отправьте дату и время публикации в формате YYYY-MM-DD HH:MM.", back_keyboard()

        if action == "show_draft":
            out = self.render_draft(draft)
            session.close()
            return out, moderation_keyboard()

        if action == "back":
            state.step = "await_review"
            draft.status = "await_review"
            out = self.render_draft(draft)
            session.close()
            return out, moderation_keyboard()

        session.close()
        return "Кнопка не распознана.", None
