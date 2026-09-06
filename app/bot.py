# app/bot.py
import logging
import time
import requests.exceptions
from typing import Any, Optional

import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.utils import get_random_id

from app.config import settings
from app.dialog import DialogManager
from app.database import init_db

logger = logging.getLogger(__name__)


def get_message_dict(event: Any) -> Optional[dict]:
    obj = getattr(event, "object", None) or getattr(event, "obj", None)
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get("message") or obj
    message = getattr(obj, "message", None)
    if message is not None:
        if isinstance(message, dict):
            return message
        return {
            "peer_id": getattr(message, "peer_id", None),
            "from_id": getattr(message, "from_id", None),
            "text": getattr(message, "text", ""),
            "payload": getattr(message, "payload", None),
            "attachments": getattr(message, "attachments", None),
        }
    return None


def send_message(vk, peer_id: int, text: str, keyboard: Optional[str] = None) -> None:
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": get_random_id(),
    }
    if keyboard:
        params["keyboard"] = keyboard
    vk.messages.send(**params)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    init_db()

    if not settings.vk_group_id or not settings.vk_group_token:
        logger.error("❌ VK_GROUP_ID или VK_GROUP_TOKEN не заданы в .env")
        return

    vk_community = vk_api.VkApi(token=settings.vk_group_token)
    vk_user = vk_api.VkApi(token=settings.vk_user_token)
    
    vk_community_api = vk_community.get_api()
    
    longpoll = VkBotLongPoll(vk_community, settings.vk_group_id)
    dialog_manager = DialogManager(vk_community, vk_user)

    from app.token_manager import token_manager
    token_manager.start_background_refresh()

    logger.info("✅ Бот успешно запущен и подключен к Long Poll. Ожидаю сообщения...")

    while True:
        try:
            for event in longpoll.listen():
                if event.type != VkBotEventType.MESSAGE_NEW:
                    continue

                msg = get_message_dict(event)
                if not msg:
                    continue

                peer_id = msg.get("peer_id")
                from_id = msg.get("from_id")
                text = (msg.get("text") or "").strip()
                payload = msg.get("payload")
                attachments = msg.get("attachments") or []

                if peer_id is None or from_id is None or from_id == -settings.vk_group_id:
                    continue

                # 🔹 ЕДИНАЯ ПРОВЕРКА ДОСТУПА В САМОМ НАЧАЛЕ
                # Если пользователя нет в ADMIN_USER_IDS, мы сразу прерываем обработку.
                # Бот ничего не ответит и не будет выполнять никакой логики.
                if not dialog_manager.is_allowed_user(from_id):
                    logger.warning(f"⛔ ПОПЫТКА ДОСТУПА: Пользователь {from_id} НЕ в белом списке. Игнорирую сообщение.")
                    continue

                response_text = None
                keyboard = None

                # 1. Команды и кнопки
                if payload or text.lower() in ["/start", "/старт", "старт", "готово", "готово к публикации", "done", "утвердить", "approve", "cancel", "отмена", "birthday", "free", "/auth", "/авторизация", "авторизация", "/check", "/статус", "/status", "/reauth", "/переавторизация"]:
                    response_text, keyboard = dialog_manager.handle_text(peer_id, from_id, text, payload)
                
                # 2. 🔹 СБОР ВЛОЖЕНИЙ С МГНОВЕННЫМ ОТВЕТОМ
                elif attachments and not text and not payload:
                    # Сразу говорим пользователю, что бот не завис
                    send_message(vk_community_api, peer_id, "⏳ Подождите, собираю и загружаю файлы...", None)
                    
                    # Добавляем в очередь
                    dialog_manager.add_to_queue(peer_id, from_id, attachments)
                    
                    # Ждем всего 1.5 секунды, чтобы VK успел "дослать" остальные файлы из пачки
                    time.sleep(1.5)
                    
                    # Забираем всё, что накопилось, и обрабатываем
                    all_attachments = dialog_manager.get_and_clear_queue(peer_id)
                    if all_attachments:
                        response_text, keyboard = dialog_manager.handle_attachments(peer_id, from_id, all_attachments)
                
                # 3. Смешанное сообщение (и текст, и вложение)
                elif attachments and text:
                    response_text = "⚠️ Я вижу и текст, и вложение. Пожалуйста, отправьте фото/видео **отдельным сообщением**."
                    draft = dialog_manager._get_draft(peer_id, from_id)
                    if draft.status == "awaiting_assets":
                        keyboard = dialog_manager._make_keyboard_assets()
                
                # 4. Обычный текст
                else:
                    response_text, keyboard = dialog_manager.handle_text(peer_id, from_id, text, payload)

                # Отправляем финальный ответ (если он есть), он заменит или дополнит сообщение "Подождите"
                if response_text is not None:
                    try:
                        send_message(vk_community_api, peer_id, response_text, keyboard)
                        logger.info(f"Отправлен финальный ответ в peer_id={peer_id}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения: {e}")

        except requests.exceptions.ReadTimeout:
            logger.warning("⚠️ Соединение с Long Poll прервалось. Переподключаюсь через 2 сек...")
            time.sleep(2)
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ Ошибка сети при подключении к Long Poll. Переподключаюсь через 2 сек...")
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в цикле Long Poll: {e}. Переподключаюсь через 5 сек...")
            time.sleep(5)


if __name__ == "__main__":
    main()