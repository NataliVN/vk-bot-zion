from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Tuple

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from app.config import settings
from app.llm_service import generate_post

logger = logging.getLogger(__name__)


@dataclass
class Draft:
    vk_user_id: int
    peer_id: int
    child_name: str = ""
    child_age: str = ""
    event_date: str = ""
    fact: str = ""
    post_text: str = ""
    status: str = "awaiting_data"
    assets_received: bool = False
    post_id: int = 0
    publish_at_text: str = ""
    publish_at_ts: int = 0
    regen_prompt: str = ""


class DialogManager:
    def __init__(self, vk_client: vk_api.VkApi):
        self.vk_client = vk_client
        self.group_api = vk_client.get_api()
        self.drafts: dict[int, Draft] = {}

    def _get_draft(self, peer_id: int, user_id: int) -> Draft:
        if peer_id not in self.drafts:
            self.drafts[peer_id] = Draft(vk_user_id=user_id, peer_id=peer_id)
        return self.drafts[peer_id]

    def _reset_draft(self, peer_id: int, user_id: int) -> Draft:
        self.drafts[peer_id] = Draft(vk_user_id=user_id, peer_id=peer_id)
        return self.drafts[peer_id]

    def is_allowed_user(self, user_id: int) -> bool:
        return user_id in settings.admin_user_ids

    def _make_keyboard_review(self) -> str:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("✅ Утвердить", color=VkKeyboardColor.POSITIVE, payload='{"action":"approve"}')
        keyboard.add_button("✏️ Редактировать", color=VkKeyboardColor.SECONDARY, payload='{"action":"edit"}')
        keyboard.add_line()
        keyboard.add_button("🔁 Перегенерировать", color=VkKeyboardColor.PRIMARY, payload='{"action":"regen"}')
        return keyboard.get_keyboard()

    def _make_keyboard_assets(self) -> str:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("Готово", color=VkKeyboardColor.POSITIVE, payload='{"action":"done"}')
        return keyboard.get_keyboard()

    def _make_keyboard_start(self) -> str:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("Создать отложенный пост", color=VkKeyboardColor.PRIMARY, payload='{"action":"start"}')
        return keyboard.get_keyboard()

    def _empty_keyboard(self) -> str:
        return VkKeyboard.get_empty_keyboard()

    def _parse_payload_action(self, payload: Any) -> str:
        if not payload:
            return ""
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
            return str(data.get("action", "")).strip().lower()
        except Exception:
            logger.exception("Не удалось разобрать payload: %r", payload)
            return ""

    def start(self, peer_id: int, user_id: int) -> Tuple[str, Optional[str]]:
        if not self.is_allowed_user(user_id):
            return "Доступ к боту закрыт. Вы общаетесь с оператором сообщества.", None

        self._reset_draft(peer_id, user_id)
        return (
            "Пришли одним сообщением:\n"
            "1) имя\n"
            "2) возраст\n"
            "3) дата мероприятия\n"
            "4) интересный факт",
            None,
        )

    def handle_text(self, peer_id: int, user_id: int, text: str, payload: Any = None) -> Tuple[str, Optional[str]]:
        draft = self._get_draft(peer_id, user_id)
        text = (text or "").strip()
        clean_text = text.lower()
        action = self._parse_payload_action(payload)

        if action == "start" or clean_text in ["/start", "/старт", "создать отложенный пост"]:
            return self.start(peer_id, user_id)

        if action == "approve":
            clean_text = "approve"
        elif action == "edit":
            clean_text = "edit"
        elif action == "regen":
            clean_text = "regen"
        elif action == "done":
            clean_text = "done"

        if draft.status == "awaiting_data":
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            if len(lines) < 4:
                return "Нужно 4 строки: имя, возраст, дата, интересный факт.", None

            draft.child_name, draft.child_age, draft.event_date, draft.fact = lines[:4]

            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name,
                    child_age=draft.child_age,
                    event_date=draft.event_date,
                    fact=draft.fact,
                )
            except Exception as e:
                logger.exception("Ошибка генерации поста")
                return f"Ошибка генерации поста: {e}", None

            draft.status = "awaiting_review"
            return (
                f"Черновик готов:\n\n{draft.post_text}\n\n"
                "Выберите действие на клавиатуре (она может быть убрана, нажмите на соответствующую иконку в поле ввода текста).",
                self._make_keyboard_review(),
            )

        if draft.status == "awaiting_review":
            if clean_text in ["/approve", "approve", "утвердить"]:
                draft.status = "awaiting_assets"
                return (
                    "Теперь пришлите фотографии и видео вложениями.",
                    self._make_keyboard_assets(),
                )

            if clean_text in ["/edit", "edit", "редактировать"]:
                draft.status = "awaiting_manual_edit"
                return (
                    "Пришли новый текст целиком (можно с форматированием).",
                    None,
                )

            if clean_text in ["/regen", "regen", "перегенерировать"]:
                draft.status = "awaiting_regen_prompt"
                return (
                    "Введите уточняющий промпт для перегенерации. Если хотите без уточнений, напишите «без» или отправьте пустое сообщение.",
                    None,
                )

            return "Используй кнопки: Утвердить, Редактировать или Перегенерировать.", self._make_keyboard_review()

        if draft.status == "awaiting_manual_edit":
            if not text:
                return "Пришли текст целиком.", None

            draft.post_text = text
            draft.status = "awaiting_review"
            return (
                f"Текст обновлён:\n\n{draft.post_text}\n\n"
                "Выберите действие на клавиатуре (она может быть убрана, нажмите на соответствующую иконку в поле ввода текста)",
                self._make_keyboard_review(),
            )

        if draft.status == "awaiting_regen_prompt":
            if not text:
                draft.regen_prompt = ""
            elif clean_text in ["без", "skip", "пропустить"]:
                draft.regen_prompt = ""
            else:
                draft.regen_prompt = text

            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name,
                    child_age=draft.child_age,
                    event_date=draft.event_date,
                    fact=draft.fact,
                    regen_prompt=draft.regen_prompt,
                )
            except Exception as e:
                logger.exception("Ошибка повторной генерации")
                draft.status = "awaiting_review"
                return f"Ошибка повторной генерации: {e}", self._make_keyboard_review()

            draft.status = "awaiting_review"
            return (
                f"Обновлённый черновик:\n\n{draft.post_text}",
                self._make_keyboard_review(),
            )

        if draft.status == "awaiting_assets":
            if clean_text in ["/done", "done", "готово"]:
                if not draft.assets_received:
                    return "Сначала пришлите хотя бы один файл, потом нажмите кнопку <Готово> (она может быть убрана, нажмите на соответствующую иконку в поле ввода текста).", self._make_keyboard_assets()

                try:
                    draft.post_id = self._create_scheduled_post(draft)
                    self._notify_operator(draft)
                    draft.status = "scheduled"
                    return (
                        f"Пост запланирован на {draft.publish_at_text}.\n"
                        f"ID записи: {draft.post_id}",
                        self._empty_keyboard(),
                    )
                except Exception as e:
                    logger.exception("Ошибка создания отложенного поста")
                    return f"Не удалось создать пост: {e}", self._make_keyboard_assets()

            return "Сейчас нужны только вложения или нажмите кнопку <Готово> (она может быть убрана, нажмите на соответствующую иконку в поле ввода текста).", self._make_keyboard_assets()

        if draft.status == "scheduled":
            return "Пост уже запланирован. Можете создать новый.", self._make_keyboard_start()

        return "Напиши /start, чтобы начать заново.", self._make_keyboard_start()

    def handle_attachments(self, peer_id: int, user_id: int, attachments: list[dict[str, Any]]) -> Tuple[str, Optional[str]]:
        draft = self._get_draft(peer_id, user_id)

        if draft.status != "awaiting_assets":
            return "Сейчас вложения не ожидаются. Сначала утверди текст.", None

        if not attachments:
            return "Вложений не найдено. Пришлите фото или видео.", self._make_keyboard_assets()

        draft.assets_received = True
        return f"Файлы приняты: {len(attachments)} шт. Теперь нажмите кнопку <Готово> (она может быть убрана, нажмите на соответствующую иконку в поле ввода текста).", self._make_keyboard_assets()

    def _create_scheduled_post(self, draft: Draft) -> int:
        draft.publish_at_ts = int(datetime.now().timestamp()) + (24 * 60 * 60)
        draft.publish_at_text = datetime.fromtimestamp(draft.publish_at_ts).strftime("%d.%m.%Y %H:%M")

        response = self.group_api.wall.post(
            owner_id=-abs(settings.vk_group_id),
            from_group=1,
            message=draft.post_text,
            publish_date=draft.publish_at_ts,
            random_id=int(datetime.now().timestamp() * 1000000),
        )
        return int(response.get("post_id", 0))

    def _get_user_full_name(self, user_id: int) -> str:
        user = self.group_api.users.get(
            user_ids=user_id,
            fields="first_name,last_name",
        )[0]
        return f"{user['first_name']} {user['last_name']}"

    def _notify_operator(self, draft: Draft, full_name: str = ""):
        post_link = f"https://vk.com/wall-{settings.vk_group_id}_{draft.post_id}"
        chat_link = f"https://vk.com/gim{settings.vk_group_id}/convo/{draft.peer_id}"
        user_link = f"https://vk.com/id{draft.vk_user_id}"

        if full_name:
            user_display = f"[id{draft.vk_user_id}|{full_name}]"
            user_line = f"Пользователь: {user_display} ({user_link})"
        else:
            user_line = f"Пользователь: {user_link}"

        message = (
            f"{user_line}\n"
            f"Диалог: {chat_link}\n"
            f"Имя ребёнка: {draft.child_name}\n"
            f"Дата мероприятия: {draft.event_date}\n"
            f"Время публикации: {draft.publish_at_text}\n"
            f"Пост: {post_link}\n\n"
            f"В этом диалоге уже отправлены фото и видео. Их нужно взять вручную из переписки."
        )

        self.group_api.messages.send(
            user_id=settings.operator_user_id,
            message=message,
            random_id=int(datetime.now().timestamp() * 1000000),
        )

        self.group_api.messages.send(
            user_id=6510108,
            message=f"VR Zion было поставлено задание: {message}",
            random_id=int(datetime.now().timestamp() * 1000000),
        )