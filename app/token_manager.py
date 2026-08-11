# app/token_manager.py
"""
Менеджер токенов с поддержкой нескольких пользователей и автоматическим обновлением.
"""
import logging
import requests
import uuid
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.database import get_user_token, save_user_token

logger = logging.getLogger(__name__)


class TokenManager:
    def __init__(self):
        # Запасной вариант: глобальный токен из .env (для обратной совместимости)
        self._global_token = getattr(settings, "vk_user_token", None)
        self._global_expires_at = datetime.utcnow() + timedelta(days=365)

    def has_token(self, vk_user_id: int) -> bool:
        """
        Проверяет, есть ли у пользователя токен в базе данных.
        """
        db_token = get_user_token(vk_user_id)
        return db_token is not None

    def check_token_health(self, vk_user_id: int) -> dict:
        """
        Проверяет реальную валидность токена через запрос к VK API.
        """
        db_token = get_user_token(vk_user_id)
        
        if not db_token:
            return {
                "status": "no_token",
                "message": "Токен не найден в базе. Требуется авторизация.",
                "user_id": None
            }
        
        try:
            token = self.get_valid_token(vk_user_id)
        except ValueError as e:
            logger.warning(f"⚠️ Токен пользователя {vk_user_id} невалиден: {e}")
            from app.database import delete_user_token
            delete_user_token(vk_user_id)
            return {
                "status": "refresh_failed",
                "message": "Токен истёк и не может быть обновлён. Требуется повторная авторизация.",
                "user_id": None
            }
        
        try:
            response = requests.post(
                "https://api.vk.com/method/users.get",
                data={"access_token": token, "v": "5.199"},
                timeout=10
            ).json()
            
            if "error" in response:
                error_code = response["error"].get("error_code")
                error_msg = response["error"].get("error_msg", "")
                
                if error_code in [5, 27]:
                    from app.database import delete_user_token
                    delete_user_token(vk_user_id)
                    return {
                        "status": "expired",
                        "message": f"VK отозвал токен: {error_msg}. Требуется повторная авторизация.",
                        "user_id": None
                    }
                
                return {
                    "status": "expired",
                    "message": f"Ошибка VK API: {error_msg}",
                    "user_id": None
                }
            
            user_info = response["response"][0]
            return {
                "status": "valid",
                "message": f"Токен валиден. Пользователь: {user_info.get('first_name', '')} {user_info.get('last_name', '')}",
                "user_id": user_info.get("id")
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки токена: {e}")
            return {
                "status": "expired",
                "message": f"Не удалось связаться с VK: {e}",
                "user_id": None
            }

    def get_valid_token(self, vk_user_id: int) -> str:
        """
        Возвращает валидный access_token для конкретного пользователя.
        Если токен истёк, автоматически обновляет его.
        """
        db_token = get_user_token(vk_user_id)
        
        if not db_token:
            logger.warning(f"⚠️ Токен для пользователя {vk_user_id} не найден в БД. Использую глобальный токен из .env")
            if not self._global_token:
                raise ValueError("Глобальный токен не настроен в .env, а пользователь не авторизован!")
            return self._global_token

        time_until_expiry = db_token.expires_at - datetime.utcnow()
        if time_until_expiry.total_seconds() < 600:  # Менее 10 минут
            logger.info(f"⏰ Токен пользователя {vk_user_id} скоро истечёт. Обновляем...")
            # 🔹 ПЕРЕДАЁМ device_id из БД (может быть None для старых записей)
            if not self._refresh_user_token(vk_user_id, db_token.refresh_token, db_token.device_id):
                logger.error(f"❌ Не удалось обновить токен для {vk_user_id}. Требуется повторная авторизация.")
                from app.database import delete_user_token
                delete_user_token(vk_user_id)
                raise ValueError(f"Токен пользователя {vk_user_id} истёк и не может быть обновлён.")
            
            db_token = get_user_token(vk_user_id)
            
            if not db_token:
                raise ValueError(f"Токен пользователя {vk_user_id} не найден после обновления")

        return db_token.access_token

    def _refresh_user_token(self, vk_user_id: int, refresh_token: str, device_id: Optional[str] = None) -> bool:
        """
        Обновляет access_token с помощью refresh_token через VK OAuth API.
        """
        app_id = settings.vk_client_id
        app_secret = settings.vk_client_secret

        if not app_id or not app_secret:
            logger.error("❌ Для обновления токенов необходимы VK_CLIENT_ID и VK_CLIENT_SECRET в файле .env")
            return False

        # 🔹 ЕСЛИ device_id НЕТ (старая запись), генерируем новый UUID
        # Это может не сработать для старых токенов, но хотя бы не упадёт
        if not device_id:
            logger.warning(f"⚠️ device_id отсутствует для пользователя {vk_user_id}. Генерирую новый UUID.")
            device_id = str(uuid.uuid4())

        try:
            logger.info(f"🔄 Запрос на обновление токена для {vk_user_id}")
            
            response = requests.post(
                "https://id.vk.com/oauth2/auth",
                data={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "device_id": device_id
                },
                timeout=15
            )
            
            logger.info(f"📥 Ответ VK при рефреше (HTTP {response.status_code}): {response.text}")
            response_data = response.json()

            if "error" in response_data:
                logger.error(f"❌ Ошибка обновления токена: {response_data.get('error')} - {response_data.get('error_description')}")
                return False

            new_access_token = response_data["access_token"]
            new_refresh_token = response_data.get("refresh_token", refresh_token)
            expires_in = response_data.get("expires_in", 86400)
            
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            success = save_user_token(vk_user_id, new_access_token, new_refresh_token, expires_at, device_id)
            
            if success:
                logger.info(f"✅ Токен пользователя {vk_user_id} успешно обновлён! (Действует {expires_in} сек)")
            
            return success

        except Exception as e:
            logger.error(f"❌ Исключение при обновлении токена: {e}")
            return False

    def exchange_code_for_token(self, vk_user_id: int, code: str, code_verifier: str, device_id: str) -> bool:
        """
        Обменивает код на токены используя PKCE и device_id из ответа VK.
        """
        app_id = settings.vk_client_id
        app_secret = settings.vk_client_secret

        try:
            logger.info(f"📤 Запрос обмена кода для {vk_user_id}:")
            logger.info(f"   client_id: {app_id}")
            logger.info(f"   client_secret: {app_secret[:4]}...{app_secret[-4:]} (длина: {len(app_secret)})")
            
            response = requests.post(
                "https://id.vk.com/oauth2/auth",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "https://oauth.vk.com/blank.html",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "device_id": device_id,
                    "code_verifier": code_verifier,
                    "state": "12345"
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15
            )
            
            logger.info(f"📥 Ответ VK при обмене (HTTP {response.status_code}): {response.text}")
            response_data = response.json()

            if "error" in response_data:
                logger.error(f"❌ Ошибка обмена кода на токен: {response_data.get('error')} - {response_data.get('error_description')}")
                return False

            access_token = response_data["access_token"]
            refresh_token = response_data.get("refresh_token", "")
            expires_in = response_data.get("expires_in", 86400)
            returned_user_id = response_data.get("user_id")

            if not refresh_token:
                logger.warning(f"⚠️ ВНИМАНИЕ! VK НЕ ВЕРНУЛ refresh_token для пользователя {vk_user_id}!")
            else:
                logger.info(f"✅ Получены токены для {vk_user_id}:")
                logger.info(f"   access_token: {access_token[:30]}...")
                logger.info(f"   refresh_token: {refresh_token[:30]}... (длина: {len(refresh_token)})")
                logger.info(f"   device_id: {device_id}")

            if returned_user_id and returned_user_id != vk_user_id:
                logger.warning(f"⚠️ ID в токене ({returned_user_id}) не совпадает с ID пользователя ({vk_user_id})")

            return self.save_new_token(vk_user_id, access_token, refresh_token, expires_in, device_id)

        except Exception as e:
            logger.error(f"❌ Исключение при обмене кода: {e}")
            return False

    def save_new_token(self, vk_user_id: int, access_token: str, refresh_token: str, expires_in_seconds: int, device_id: Optional[str] = None) -> bool:
        """
        Сохраняет новый токен после первичной авторизации пользователя.
        """
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        return save_user_token(vk_user_id, access_token, refresh_token, expires_at, device_id)

    def start_background_refresh(self):
        """
        Заглушка для обратной совместимости.
        """
        logger.info("ℹ️ Фоновое обновление токенов теперь происходит автоматически при каждом запросе")


# Глобальный экземпляр для импорта в других модулях
token_manager = TokenManager()