import json
import logging
from typing import Any, Optional

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

from app.config import settings

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def make_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("1", color=VkKeyboardColor.PRIMARY, payload='{"button":"1"}')
    keyboard.add_button("2", color=VkKeyboardColor.PRIMARY, payload='{"button":"2"}')
    return keyboard.get_keyboard()


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
    if not settings.vk_group_token:
        logger.error("VK_GROUP_TOKEN не задан в .env")
        return

    if not settings.vk_group_id:
        logger.error("VK_GROUP_ID не задан в .env")
        return

    vk_session = vk_api.VkApi(token=settings.vk_group_token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, settings.vk_group_id)

    logger.info("Бот запущен. Ожидаю сообщения...")

    for event in longpoll.listen():
        logger.debug("Получено событие: type=%s, event=%s", event.type, event)

        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        msg = get_message_dict(event)
        if not msg:
            logger.warning(
                "Не удалось получить message. object=%r obj=%r",
                getattr(event, "object", None),
                getattr(event, "obj", None),
            )
            continue

        peer_id = msg.get("peer_id")
        from_id = msg.get("from_id")
        text = (msg.get("text") or "").strip()
        payload = msg.get("payload")

        logger.debug(
            "message fields: peer_id=%r, from_id=%r, text=%r, payload=%r",
            peer_id, from_id, text, payload
        )

        if peer_id is None or from_id is None:
            logger.warning("Не удалось получить peer_id или from_id")
            continue

        if from_id == -settings.vk_group_id:
            continue

        clean_text = text.lower()
        response_text = None
        keyboard = None

        if clean_text in ["/start", "/старт"]:
            response_text = "Привет! Это бот. Выберите кнопку:"
            keyboard = make_keyboard()
        elif clean_text == "1":
            response_text = "Вы нажали 1"
        elif clean_text == "2":
            response_text = "Вы нажали 2"
        elif payload:
            try:
                data = json.loads(payload) if isinstance(payload, str) else payload
                button = str(data.get("button", ""))
                if button == "1":
                    response_text = "Вы нажали 1"
                elif button == "2":
                    response_text = "Вы нажали 2"
            except Exception:
                logger.exception("Не удалось разобрать payload: %r", payload)

        if response_text is None:
            response_text = "Напишите /start"

        try:
            send_message(vk, peer_id, response_text, keyboard)
            logger.info("Отправлено сообщение в peer_id=%s", peer_id)
        except vk_api.exceptions.ApiError as e:
            logger.exception("API ошибка VK: %s", e)
            if e.code == 912:
                logger.error("Ошибка 912: включите сообщения сообщества и режим бота в настройках группы.")
        except Exception as e:
            logger.exception("Неожиданная ошибка отправки: %s", e)


if __name__ == "__main__":
    main()
