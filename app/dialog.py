# app/dialog.py
from __future__ import annotations

import json
import logging
import os
import requests
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from app.config import settings
from app.llm_service_yandex import generate_post
from app.token_manager import token_manager

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
    attachment_string: str = ""
    post_id: int = 0
    publish_at_text: str = ""
    publish_at_ts: int = 0
    regen_prompt: str = ""


class DialogManager:
    def __init__(self, vk_community: vk_api.VkApi, vk_user: vk_api.VkApi):
        self.community_api = vk_community.get_api()
        self.user_api = vk_user.get_api()
        self.drafts: dict[int, Draft] = {}
        self.queues: dict[int, list] = {}

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
        keyboard.add_line()
        keyboard.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE, payload='{"action":"cancel"}')
        return keyboard.get_keyboard()

    def _make_keyboard_time(self) -> str:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("📅 Завтра в это же время", color=VkKeyboardColor.PRIMARY, payload='{"action":"tomorrow"}')
        keyboard.add_line()
        keyboard.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE, payload='{"action":"cancel"}')
        return keyboard.get_keyboard()

    def _make_keyboard_assets(self) -> str:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("Готово к публикации", color=VkKeyboardColor.POSITIVE, payload='{"action":"done"}')
        keyboard.add_line()
        keyboard.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE, payload='{"action":"cancel"}')
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
            return ""

    def start(self, peer_id: int, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        if not self.is_allowed_user(user_id):
            return None, None
        self._reset_draft(peer_id, user_id)
        return "Пришли одним сообщением 4 строки:\n1) имя\n2) возраст\n3) дата мероприятия\n4) интересный факт\n\nИли нажмите ❌ Отмена", None

    def handle_text(self, peer_id: int, user_id: int, text: str, payload: Any = None) -> Tuple[Optional[str], Optional[str]]:
        if not self.is_allowed_user(user_id):
            return None, None

        draft = self._get_draft(peer_id, user_id)
        text = (text or "").strip()
        clean_text = text.lower()
        action = self._parse_payload_action(payload)

        if action == "start" or clean_text in ["/start", "/старт", "создать отложенный пост"]:
            return self.start(peer_id, user_id)
        if action == "cancel":
            self._reset_draft(peer_id, user_id)
            return "🛑 Создание поста отменено. Вы можете начать заново, нажав /start", self._make_keyboard_start()

        if action == "approve": clean_text = "approve"
        elif action == "edit": clean_text = "edit"
        elif action == "regen": clean_text = "regen"
        elif action == "done": clean_text = "done"

        if draft.status == "awaiting_data":
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            if len(lines) < 4:
                return "Нужно 4 строки: имя, возраст, дата, интересный факт.", None
            draft.child_name, draft.child_age, draft.event_date, draft.fact = lines[:4]
            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name, child_age=draft.child_age,
                    event_date=draft.event_date, fact=draft.fact,
                )
            except Exception as e:
                logger.exception("Ошибка генерации поста")
                return f"Ошибка генерации поста: {e}", None
            draft.status = "awaiting_review"
            return f"Черновик готов:\n\n{draft.post_text}\n\nВыберите действие:", self._make_keyboard_review()

        if draft.status == "awaiting_review":
            if clean_text in ["/approve", "approve", "утвердить"]:
                draft.status = "awaiting_time"
                return "Отлично! Теперь укажите дату и время публикации.\n\nВы можете нажать кнопку «📅 Завтра в это же время» ниже,\nили ввести вручную в формате: ДД.ММ ЧЧ:ММ (например: 25.08 18:30)", self._make_keyboard_time()
            if clean_text in ["/edit", "edit", "редактировать"]:
                draft.status = "awaiting_manual_edit"
                return "Пришли новый текст целиком.", None
            if clean_text in ["/regen", "regen", "перегенерировать"]:
                draft.status = "awaiting_regen_prompt"
                return "Введите уточняющий промпт. Если без уточнений, напишите «без».", None
            return "Используй кнопки: Утвердить, Редактировать, Перегенерировать или Отмена.", self._make_keyboard_review()

        if draft.status == "awaiting_time":
            if action == "tomorrow":
                tomorrow = datetime.now() + timedelta(days=1)
                draft.publish_at_ts = int(tomorrow.timestamp())
                draft.publish_at_text = tomorrow.strftime("Завтра, %d.%m.%Y в %H:%M")
                draft.status = "awaiting_assets"
                return f"⏰ Отлично! Пост будет опубликован: {draft.publish_at_text}\n\nТеперь пришлите фото и/или видео отдельным сообщением.", self._make_keyboard_assets()
            try:
                dt_obj = datetime.strptime(text, "%d.%m %H:%M").replace(year=datetime.now().year)
                if dt_obj.timestamp() <= datetime.now().timestamp():
                    return "⚠️ Указанное время уже прошло. Укажите дату в будущем (ДД.ММ ЧЧ:ММ) или нажмите «Завтра».", self._make_keyboard_time()
                draft.publish_at_ts = int(dt_obj.timestamp())
                draft.publish_at_text = dt_obj.strftime("%d.%m.%Y в %H:%M")
                draft.status = "awaiting_assets"
                return f"⏰ Отлично! Пост будет опубликован: {draft.publish_at_text}\n\nТеперь пришлите фото и/или видео отдельным сообщением.", self._make_keyboard_assets()
            except ValueError:
                return "⚠️ Неверный формат. Введите как ДД.ММ ЧЧ:ММ (например: 25.08 18:30)\nИли нажмите кнопку «📅 Завтра в это же время».", self._make_keyboard_time()

        if draft.status == "awaiting_manual_edit":
            if not text:
                return "Пришли текст целиком.", None
            draft.post_text = text
            draft.status = "awaiting_review"
            return f"Текст обновлён:\n\n{draft.post_text}", self._make_keyboard_review()

        if draft.status == "awaiting_regen_prompt":
            draft.regen_prompt = "" if not text or clean_text in ["без", "skip", "пропустить"] else text
            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name, child_age=draft.child_age,
                    event_date=draft.event_date, fact=draft.fact, regen_prompt=draft.regen_prompt
                )
            except Exception as e:
                draft.status = "awaiting_review"
                return f"Ошибка повторной генерации: {e}", self._make_keyboard_review()
            draft.status = "awaiting_review"
            return f"Обновлённый черновик:\n\n{draft.post_text}", self._make_keyboard_review()

        if draft.status == "awaiting_assets":
            if clean_text in ["/done", "done", "готово", "готово к публикации"]:
                if not draft.assets_received:
                    return "Сначала пришлите хотя бы одно фото или видео, потом нажмите <Готово к публикации>.", self._make_keyboard_assets()
                try:
                    draft.post_id = self._create_scheduled_post(draft)
                    self._notify_operators(draft)
                    draft.status = "scheduled"
                    post_link = f"https://vk.com/wall-{abs(settings.vk_group_id)}_{draft.post_id}"
                    return (
                        f"🎉 Отлично! Пост успешно создан и запланирован.\n\n"
                        f"📅 Дата публикации: {draft.publish_at_text}\n"
                        f"🔗 Ссылка на отложенный пост: {post_link}\n\n"
                        f"Вы можете начать создание нового поста, нажав кнопку ниже."
                    ), self._make_keyboard_start()
                except Exception as e:
                    logger.exception("Ошибка создания отложенного поста")
                    return f"Не удалось создать пост: {e}", self._make_keyboard_assets()
            return "Пришлите фото или видео, или нажмите <Готово к публикации>.", self._make_keyboard_assets()

        if draft.status == "scheduled":
            return "Пост уже запланирован. Можете создать новый.", self._make_keyboard_start()
        
        return "Напиши /start, чтобы начать заново.", self._make_keyboard_start()

    # 🔹 МЕТОДЫ ОЧЕРЕДИ
    def add_to_queue(self, peer_id: int, user_id: int, attachments: list):
        if peer_id not in self.queues:
            self.queues[peer_id] = []
        self.queues[peer_id].extend(attachments)
        logger.info(f"📥 Добавлено {len(attachments)} вложений в очередь. Всего: {len(self.queues[peer_id])}")

    def get_and_clear_queue(self, peer_id: int) -> list:
        if peer_id in self.queues:
            attachments = self.queues[peer_id][:]
            self.queues[peer_id] = []
            logger.info(f"📤 Получено {len(attachments)} вложений из очереди для обработки")
            return attachments
        return []

    def handle_attachments(self, peer_id: int, user_id: int, attachments: list[dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        if not self.is_allowed_user(user_id):
            return None, None
        draft = self._get_draft(peer_id, user_id)
        
        if draft.status == "awaiting_time":
            return "⏳ Сначала выберите время публикации, а затем присылайте фото.", self._make_keyboard_time()
        if draft.status != "awaiting_assets":
            return "Сейчас вложения не ожидаются. Сначала утвердите текст.", None
        if not attachments:
            return "Вложений не найдено. Пришлите фото или видео.", None

        os.makedirs(settings.upload_dir, exist_ok=True)
        new_attachment_strings, success_names, fail_names = [], [], []
        group_id = abs(int(settings.vk_group_id))
        user_token = token_manager.get_valid_token()

        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
            heic_support = True
        except Exception:
            heic_support = False

        logger.info(f"📋 Получено вложений в пакете: {len(attachments)}")

        for i, att in enumerate(attachments):
            att_type = att.get("type")
            #att_name = f"Фото {i+1}" if att_type == "photo" else (f"Видео {i+1}" if att_type == "video" else (f"Файл {att.get('doc', {}).get('ext', 'файл').upper()} {i+1}" if att_type == "doc" else f"Вложение {i+1}")
            
            if att_type == "photo":
                att_name = f"Фото {i+1}"
            elif att_type == "video":
                att_name = f"Видео {i+1}"
            elif att_type == "doc":
                doc_ext = att.get("doc", {}).get("ext", "файл").upper()
                att_name = f"Файл {doc_ext} {i+1}"
            else:
                att_name = f"Вложение {i+1}"
            
            logger.info(f"🔄 Начинаю обработку: {att_name} (type: {att_type})")
            
            if i > 0:
                time.sleep(1.0) # Микро-пауза между файлами

            try:
                if att_type == "photo":
                    from PIL import Image
                    photo_data = att.get("photo", {})
                    sizes = photo_data.get("sizes", [])
                    if not sizes:
                        raise Exception("Нет размеров")
                    best_size = max(sizes, key=lambda x: x.get('width', 0))
                    url = best_size.get('url')
                    photo_id = photo_data.get("id")
                    content_type = requests.head(url, timeout=5).headers.get('Content-Type', '').lower()
                    file_ext = 'heic' if 'heic' in content_type else ('png' if 'png' in content_type else 'jpg')
                    filename = os.path.join(settings.upload_dir, f"temp_p_{photo_id}_{i}.{file_ext}")
                    final_filename = os.path.join(settings.upload_dir, f"temp_p_{photo_id}_{i}.jpg")

                    response = requests.get(url, timeout=15)
                    response.raise_for_status()
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    
                    if file_ext in ['heic', 'heif', 'png', 'webp']:
                        img = Image.open(filename)
                        if img.mode in ('RGBA', 'P', 'LA'):
                            img = img.convert('RGB')
                        img.save(final_filename, 'JPEG', quality=95)
                        if os.path.exists(filename):
                            os.remove(filename)
                        filename = final_filename

                    resp_get = requests.get('https://api.vk.com/method/photos.getWallUploadServer', params={'group_id': group_id, 'access_token': user_token, 'v': '5.199'}, timeout=15)
                    if resp_get.status_code != 200:
                        raise Exception(f"HTTP {resp_get.status_code}")
                    upload_url_resp = resp_get.json()
                    if 'error' in upload_url_resp:
                        raise Exception(upload_url_resp['error']['error_msg'])
                    
                    upload_resp_data = None
                    for attempt in range(3):
                        with open(filename, 'rb') as f:
                            resp_post = requests.post(upload_url_resp['response']['upload_url'], files={'photo': f}, timeout=15)
                        if resp_post.status_code != 200:
                            if attempt < 2:
                                time.sleep(1)
                            continue
                        try:
                            upload_resp_data = resp_post.json()
                        except requests.exceptions.JSONDecodeError:
                            if attempt < 2:
                                time.sleep(1)
                            continue
                        if 'photo' in upload_resp_data and upload_resp_data.get('photo'):
                            break
                        if attempt < 2:
                            time.sleep(1)
                    
                    if not upload_resp_data or 'photo' not in upload_resp_data or not upload_resp_data.get('photo'):
                        raise Exception("VK вернул пустой параметр photo")

                    resp_save = requests.post('https://api.vk.com/method/photos.saveWallPhoto', data={'group_id': group_id, 'server': upload_resp_data['server'], 'photo': upload_resp_data['photo'], 'hash': upload_resp_data['hash'], 'access_token': user_token, 'v': '5.199'}, timeout=15)
                    if resp_save.status_code != 200:
                        raise Exception(f"HTTP {resp_save.status_code}")
                    try:
                        save_resp = resp_save.json()
                    except requests.exceptions.JSONDecodeError:
                        raise Exception("VK вернул не-JSON")
                    if 'error' in save_resp:
                        raise Exception(save_resp['error'].get('error_msg'))

                    saved = save_resp['response'][0]
                    att_str = f"photo{saved['owner_id']}_{saved['id']}" + (f"_{saved['access_key']}" if 'access_key' in saved else "")
                    new_attachment_strings.append(att_str)
                    success_names.append(att_name)
                    logger.info(f"✅ {att_name} успешно загружено: {att_str}")

                elif att_type == "doc":
                    from PIL import Image
                    doc_data = att.get("doc", {})
                    doc_ext = doc_data.get("ext", "").lower()
                    doc_url = doc_data.get("url", "")
                    doc_id = doc_data.get("id")
                    if doc_ext in ['heic', 'heif', 'png', 'jpg', 'jpeg', 'webp'] and doc_url:
                        filename = os.path.join(settings.upload_dir, f"temp_d_{doc_id}_{i}.{doc_ext}")
                        final_filename = os.path.join(settings.upload_dir, f"temp_d_{doc_id}_{i}.jpg")
                        resp_doc = requests.get(doc_url, timeout=15)
                        resp_doc.raise_for_status()
                        with open(filename, "wb") as f:
                            f.write(resp_doc.content)
                        if doc_ext in ['heic', 'heif', 'png', 'webp']:
                            img = Image.open(filename)
                            if img.mode in ('RGBA', 'P', 'LA'):
                                img = img.convert('RGB')
                            img.save(final_filename, 'JPEG', quality=95)
                            if os.path.exists(filename):
                                os.remove(filename)
                            filename = final_filename

                        resp_get = requests.get('https://api.vk.com/method/photos.getWallUploadServer', params={'group_id': group_id, 'access_token': user_token, 'v': '5.199'}, timeout=15)
                        if resp_get.status_code != 200:
                            raise Exception(f"HTTP {resp_get.status_code}")
                        upload_url_resp = resp_get.json()
                        if 'error' in upload_url_resp:
                            raise Exception(upload_url_resp['error']['error_msg'])
                        
                        upload_resp_data = None
                        for attempt in range(3):
                            with open(filename, 'rb') as f:
                                resp_post = requests.post(upload_url_resp['response']['upload_url'], files={'photo': f}, timeout=15)
                            if resp_post.status_code != 200:
                                if attempt < 2:
                                    time.sleep(1)
                                continue
                            try:
                                upload_resp_data = resp_post.json()
                            except requests.exceptions.JSONDecodeError:
                                if attempt < 2:
                                    time.sleep(1)
                                continue
                            if 'photo' in upload_resp_data and upload_resp_data.get('photo'):
                                break
                            if attempt < 2:
                                time.sleep(1)
                        
                        if not upload_resp_data or 'photo' not in upload_resp_data or not upload_resp_data.get('photo'):
                            raise Exception("VK вернул пустой параметр photo")

                        resp_save = requests.post('https://api.vk.com/method/photos.saveWallPhoto', data={'group_id': group_id, 'server': upload_resp_data['server'], 'photo': upload_resp_data['photo'], 'hash': upload_resp_data['hash'], 'access_token': user_token, 'v': '5.199'}, timeout=15)
                        if resp_save.status_code != 200:
                            raise Exception(f"HTTP {resp_save.status_code}")
                        try:
                            save_resp = resp_save.json()
                        except requests.exceptions.JSONDecodeError:
                            raise Exception("VK вернул не-JSON")
                        if 'error' in save_resp:
                            raise Exception(save_resp['error'].get('error_msg'))

                        saved = save_resp['response'][0]
                        att_str = f"photo{saved['owner_id']}_{saved['id']}" + (f"_{saved['access_key']}" if 'access_key' in saved else "")
                        new_attachment_strings.append(att_str)
                        success_names.append(att_name)
                        logger.info(f"✅ {att_name} успешно загружено: {att_str}")
                    else:
                        raise Exception("Неподдерживаемый формат или нет URL")

                elif att_type == "video":
                    video_data = att.get("video", {})
                    v_id, o_id = video_data.get("id"), video_data.get("owner_id")
                    if o_id and v_id:
                        att_str = f"video{o_id}_{v_id}" + (f"_{video_data.get('access_key')}" if video_data.get('access_key') else "")
                        new_attachment_strings.append(att_str)
                        success_names.append(att_name)
                        logger.info(f"✅ {att_name} добавлено: {att_str}")
                else:
                    raise Exception("Неизвестный тип вложения")
            except Exception as e:
                logger.error(f"❌ {att_name} ошибка: {e}")
                fail_names.append(att_name)
            finally:
                if 'filename' in locals():
                    for f in [filename, final_filename if 'final_filename' in locals() else None]:
                        if f and os.path.exists(f): 
                            try:
                                os.remove(f)
                            except:
                                pass

        if not new_attachment_strings:
            return "❌ Не удалось обработать ни один файл. Проверьте формат или отправьте по одному.", None

        current = [x for x in draft.attachment_string.split(",") if x] if draft.attachment_string else []
        for new_att in new_attachment_strings:
            if new_att not in current:
                current.append(new_att)
        draft.attachment_string = ",".join(current)
        draft.assets_received = True
        
        total = len(current)
        logger.info(f"📎 ИТОГО в очереди: {total}. Строка: {draft.attachment_string}")
        
        report_lines = [f"✅ Обработано файлов: {len(success_names)} из {len(attachments)}."]
        if success_names:
            report_lines.append(f"Успешно: {', '.join(success_names)}")
        if fail_names:
            report_lines.append(f"⚠️ Не удалось загрузить: {', '.join(fail_names)}.")
            report_lines.append("💡 Пожалуйста, отправьте эти файлы **отдельным сообщением**, чтобы я мог их добавить.")
        report_lines.append(f"\nВсего в очереди для поста: {total} шт.")
        report_lines.append("Можете добавить ещё или нажать <Готово к публикации>.")
        
        return "\n".join(report_lines), self._make_keyboard_assets()

    def _create_scheduled_post(self, draft: Draft) -> int:
        user_token = token_manager.get_valid_token()
        post_params = {
            "owner_id": -abs(int(settings.vk_group_id)), 
            "from_group": 1,
            "message": draft.post_text,
            "publish_date": draft.publish_at_ts,
            "random_id": int(time.time() * 1000000),
            "access_token": user_token,
            "v": "5.199"
        }
        if draft.attachment_string:
            post_params["attachments"] = draft.attachment_string
            
        response = requests.post("https://api.vk.com/method/wall.post", data=post_params).json()
        if "error" in response:
            raise Exception(f"Ошибка wall.post: {response['error'].get('error_msg', response['error'])}")
        return int(response["response"].get("post_id", 0))

    def _notify_operators(self, draft: Draft):
        post_link = f"https://vk.com/wall-{abs(settings.vk_group_id)}_{draft.post_id}"
        chat_link = f"https://vk.com/gim{settings.vk_group_id}/convo/{draft.peer_id}"
        user_link = f"https://vk.com/id{draft.vk_user_id}"
        user_display = f"[id{draft.vk_user_id}|ID: {draft.vk_user_id}]"
        
        # ТЕГИ <b> УДАЛЕНЫ
        message = (
            f"📢 Создан новый отложенный пост!\n\n"
            f"👤 Автор: {user_display} ({user_link})\n"
            f"💬 Диалог: {chat_link}\n"
            f"👶 Имя ребёнка: {draft.child_name}\n"
            f"📅 Дата мероприятия: {draft.event_date}\n"
            f"⏰ Публикация: {draft.publish_at_text}\n"
            f"🔗 Ссылка на пост: {post_link}\n\n"
            f"✅ Все вложения успешно прикреплены."
        )

        for op_id in settings.operator_user_ids:
            try:
                self.community_api.messages.send(
                    user_id=op_id,
                    message=message,
                    random_id=int(time.time() * 1000000)
                )
                logger.info(f"Уведомление отправлено оператору {op_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление оператору {op_id}: {e}")