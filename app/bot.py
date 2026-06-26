import logging
import time

from vk_api import VkApi
from vk_api.longpoll import VkLongPoll, VkEventType

from app.config import settings
from app.dialog import DialogManager

logger = logging.getLogger(__name__)


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_attachments(raw_attachments):
    if not raw_attachments:
        return []
    normalized = []
    for att in raw_attachments:
        if isinstance(att, dict):
            normalized.append(att)
        elif isinstance(att, str):
            normalized.append({"type": "raw", "raw": att})
    return normalized


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    while True:
        try:
            vk_session = VkApi(
                token=settings.vk_group_token,
                api_version=settings.vk_api_version,
            )
            vk = vk_session.get_api()
            longpoll = VkLongPoll(vk_session)
            dialog_manager = DialogManager(vk_session)

            logger.info("Бот запущен")

            for event in longpoll.listen():
                try:
                    if event.type != VkEventType.MESSAGE_NEW or not event.to_me or not event.from_user:
                        continue

                    peer_id = _safe_int(getattr(event, "peer_id", None))
                    user_id = _safe_int(getattr(event, "user_id", None))
                    text = (getattr(event, "text", "") or "").strip()
                    attachments = _normalize_attachments(getattr(event, "attachments", None))

                    if peer_id is None or user_id is None:
                        continue

                    if text.lower() == "/start":
                        message, _ = dialog_manager.start(peer_id, user_id)
                    elif attachments:
                        replies = dialog_manager.handle_attachments(peer_id, user_id, attachments)
                        message = "\n".join(replies) if replies else "Вложения приняты."
                    else:
                        message, _ = dialog_manager.handle_text(peer_id, user_id, text)

                    vk.messages.send(
                        peer_id=peer_id,
                        message=message,
                        random_id=int(time.time() * 1000000),
                    )

                except Exception as inner_e:
                    logger.exception("Ошибка обработки события: %s", inner_e)

        except KeyboardInterrupt:
            logger.info("Остановка вручную")
            break
        except Exception as e:
            logger.exception("Критическая ошибка бота: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
