from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import vk_api
import requests
from typing import Any, Optional
from app.llm_service import generate_post

logger = logging.getLogger(__name__)
from app.config import settings


@dataclass
class Draft:
    vk_user_id: int
    peer_id: int
    child_name: str = ""
    child_age: str = ""
    event_date: str = ""
    fact: str = ""
    photos_count: int = 0
    video_count: int = 0
    publish_at_text: str = ""
    publish_at_ts: int = 0
    post_text: str = ""
    photos: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    status: str = "awaiting_data"


class DialogManager:
    def __init__(self, vk_client: vk_api.VkApi):
        self.vk_client = vk_client
        self.group_api = vk_client.get_api()

        self.drafts: dict[int, Draft] = {}

    def _get_draft(self, peer_id: int, user_id: int) -> Draft:
        if peer_id not in self.drafts:
            self.drafts[peer_id] = Draft(vk_user_id=user_id, peer_id=peer_id)
        return self.drafts[peer_id]

    def save_incoming_photo(self, url: str) -> str:
        filename = url.split("?")[0].split("/")[-1] or "photo.jpg"
        path = Path("media") / filename
        Path("media").mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        path.write_bytes(resp.content)
        return str(path)

    # ✅ Шаг 1: /start
    def start(self, peer_id: int, user_id: int):
        self._get_draft(peer_id, user_id)
        return (
            "Привет! Пришли одним сообщением:\n"
            "1) имя ребенка\n"
            "2) возраст\n"
            "3) дата мероприятия\n"
            "4) интересный факт (можно пропустить)\n\n"
            "Пример:\nАнна\n12\n25.06.2026\nМного гостей",
            None,
        )

    # ✅ Шаг 2: сбор данных → генерация поста
    def handle_text(self, peer_id: int, user_id: int, text: str):
        draft = self._get_draft(peer_id, user_id)
        text = (text or "").strip()

        if draft.status == "awaiting_data":
            lines = [p.strip() for p in text.splitlines() if p.strip()]
            if len(lines) < 3:
                return (
                    "Нужно хотя бы 3 строки:\n"
                    "1) имя ребенка\n"
                    "2) возраст\n"
                    "3) дата мероприятия\n"
                    "(остальные можно опустить)",
                    None,
                )

            draft.child_name = lines[0]
            draft.child_age = lines[1]
            draft.event_date = lines[2]

            if len(lines) >= 4:
                draft.fact = lines[3]

            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name,
                    child_age=draft.child_age,
                    event_date=draft.event_date,
                    fact=draft.fact,
                    photos_count=draft.photos_count,
                )
            except Exception as e:
                logger.exception("LLM error")
                return f"Ошибка генерации поста: {e}. Попробуй еще раз.", None

            draft.status = "awaiting_confirm"
            return (
                "Черновик готов:\n\n"
                f"{draft.post_text}\n\n"
                "Напиши:\n"
                "✅ `/confirm` — перейдем к загрузке фото/видео\n"
                "✏️ `/edit` — редактировать текст",
                None,
            )

        if draft.status == "awaiting_confirm":
            if text == "/confirm":
                draft.status = "awaiting_photos"
                return (
                    "Понял. Теперь пришлите фото и видео (до 10 штук). "
                    "Если не нужно — `/skip`.",
                    None,
                )
            if text == "/edit":
                draft.status = "awaiting_edit"
                return (
                    "Хорошо. Напиши, что нужно изменить в тексте. "
                    "Я обновлю пост и отвечу вам.",
                    None,
                )
            return "Нажмите `/confirm` для подтверждения или `/edit` для редактирования.", None

        if draft.status == "awaiting_edit":
            draft.fact = text if text else draft.fact
            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name,
                    child_age=draft.child_age,
                    event_date=draft.event_date,
                    fact=draft.fact,
                    photos_count=draft.photos_count,
                )
            except Exception as e:
                logger.exception("LLM error during edit")
                return f"Ошибка генерации поста: {e}. Попробуй еще раз.", None

            draft.status = "awaiting_confirm"
            return (
                "Текст обновлён:\n\n"
                f"{draft.post_text}\n\n"
                "Напиши:\n"
                "✅ `/confirm` — перейдем к загрузке фото/видео\n"
                "✏️ `/edit` — редактировать текст",
                None,
            )

        if draft.status == "awaiting_photos":
            if text == "/skip":
                draft.status = "awaiting_publish_time"
                return "Ок. Пропущено. Теперь напиши дату и время публикации (например: 25.06.2026 18:30).", None
            return "Чтобы продолжить, отправь /skip (пропустить).", None

        if draft.status == "awaiting_publish_time":
            return self._set_publish_time(draft, text)

        return "Напиши /start, чтобы начать заново.", None

    def _set_publish_time(self, draft: Draft, text: str):
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H.%M", "%d-%m-%Y %H:%M"):
            try:
                dt = datetime.strptime(text.strip(), fmt)
                publish_at_text = text.strip()
                publish_at_ts = int(dt.timestamp())
                break
            except ValueError:
                continue
        else:
            return "Укажи дату и время в формате: 25.06.2026 18:30", None

        draft.publish_at_text = publish_at_text
        draft.publish_at_ts = publish_at_ts

        try:
            post_id = self._schedule_post(draft)
        except Exception as e:
            logger.exception("Failed to schedule post")
            return f"Не удалось отправить пост в отложенные: {e}", None

        draft.status = "scheduled"
        return (
            f"✅ Пост отправлен в отложенную публикацию на {draft.publish_at_text}.\n"
            f"ID: {post_id}",
            None,
        )

    def _schedule_post(self, draft: Draft):
        attachments = []

        # 📷 Фото
        for path in draft.photos[:10]:
            try:
                vk_attachment = self._upload_photo_group_token(path)
                attachments.append(vk_attachment)
            except Exception as e:
                logger.warning(f"Failed to upload photo {path}: {e}")

        # 🎥 Видео
        for path in draft.videos[:10]:
            try:
                vk_attachment = self._upload_video_group_token(path)
                if vk_attachment:
                    attachments.append(vk_attachment)
            except Exception as e:
                logger.warning(f"Failed to upload video {path}: {e}")

        group_id_int = int(settings.vk_group_id)
        params = {
            "owner_id": -abs(group_id_int),
            "from_group": 1,
            "message": draft.post_text,
            "publish_date": draft.publish_at_ts,
            "random_id": int.from_bytes(b"rand", "little"),
        }
        if attachments:
            params["attachments"] = ",".join(attachments)

        try:
            response = self.group_api.wall.post(**params)
            return response.get("post_id", 0)
        except Exception as e:
            logger.exception("wall.post error")
            return 0

    def _upload_photo_group_token(self, path: str) -> str:
        """Загрузка фото через токен сообщества: photos.getUploadServer + photos.save"""
        group_id_int = int(settings.vk_group_id)

        upload_server = self.group_api.photos.getUploadServer(group_id=group_id_int)
        upload_url = upload_server["upload_url"]

        with open(path, "rb") as f:
            resp = requests.post(upload_url, files={"photo": f}, timeout=120)
        data = resp.json()

        saved = self.group_api.photos.save(
            group_id=group_id_int,
            server=data["server"],
            photo=data["photo"],
            hash=data["hash"],
        )

        photo = saved[0]  # photos.save возвращает список
        return f"photo{photo['owner_id']}_{photo['id']}"

    def _upload_video_group_token(self, path: str) -> str:
        """
        Загрузка видео через токен сообщества.
        Поток:
          1. video.save → получаем upload_url
          2. POST на upload_url → загружаем файл
          3. Ждём обработки видео (цикл с проверкой video.get)
          4. Формируем attachment: video{owner_id}_{id}
        """
        group_id_int = int(settings.vk_group_id)
        file_size = Path(path).stat().st_size

        logger.info(f"Начинаем загрузку видео: {path} (размер: {file_size} байт)")

        # 1. Получаем URL для загрузки
        upload_info = self.group_api.video.save(
            name=Path(path).name,
            description="Видео с праздника",
            is_private=0,
            group_id=group_id_int,
            file_size=file_size,
        )
        upload_url = upload_info.get("upload_url")
        if not upload_url:
            logger.error("❌ Не получен upload_url для видео")
            return ""

        # 2. Загружаем файл на сервер VK
        with open(path, "rb") as f:
            resp = requests.post(upload_url, files={"video_file": f}, timeout=300)
        resp.raise_for_status()
        data = resp.json()

        video_id = data.get("video_id")
        owner_id = data.get("owner_id")
        if not video_id or not owner_id:
            logger.error(f"❌ Не получены video_id/owner_id после загрузки: {data}")
            return ""

        logger.info(f"Файл загружен. video_id={video_id}, owner_id={owner_id}. Ждём обработки...")

        # 3. Ждём, пока видео обработается
        max_wait_seconds = 600  # 10 минут максимум
        check_interval = 5
        elapsed = 0
        while elapsed < max_wait_seconds:
            video_info = self.group_api.video.get(
                videos=f"{owner_id}_{video_id}",
                extended=0,
            )
            items = video_info.get("items", [])
            if not items:
                logger.warning("Видео не найдено в ответе video.get — пробуем дальше")
                time.sleep(check_interval)
                elapsed += check_interval
                continue

            item = items[0]
            processing = item.get("processing", False)
            if processing:
                logger.debug("Видео ещё обрабатывается...")
                time.sleep(check_interval)
                elapsed += check_interval
            else:
                # Обработка завершена
                logger.info("✅ Видео обработано")
                break
        else:
            logger.error("⚠️ Таймаут ожидания обработки видео")

        return f"video{owner_id}_{video_id}"

    def add_photo_paths(self, peer_id: int, user_id: int, photo_paths: list[str]):
        draft = self._get_draft(peer_id, user_id)
        draft.photos.extend(photo_paths)
        return f"✅ Принято фото: {len(photo_paths)}. Теперь пришлите видео (если есть) или /skip.", None

    def add_video_paths(self, peer_id: int, user_id: int, video_paths: list[str]):
        draft = self._get_draft(peer_id, user_id)
        draft.videos.extend(video_paths)
        return f"✅ Принято видео: {len(video_paths)}. Теперь пришлите /skip или дату публикации.", None
