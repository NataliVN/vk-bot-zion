# app/token_manager.py
"""
Менеджер токенов с поддержкой нескольких пользователей и автоматическим обновлением.
"""
import logging
import requests
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
        
        # Пробуем получить валидный токен (с автообновлением, если нужно)
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
        
        # Делаем реальный запрос к VK API для проверки
        try:
            response = requests.post(
                "https://api.vk.com/method/users.get",
                data={"access_token": token, "v": "5.199"},
                timeout=10
            ).json()
            
            if "error" in response:
                error_code = response["error"].get("error_code")
                error_msg = response["error"].get("error_msg", "")
                
                if error_code in [5, 27]:  # 5 = auth error, 27 = scope missing
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
        if time_until_expiry.total_seconds() < 600:
            logger.info(f"⏰ Токен пользователя {vk_user_id} скоро истечёт. Обновляем...")
            if not self._refresh_user_token(vk_user_id, db_token.refresh_token):
                logger.error(f"❌ Не удалось обновить токен для {vk_user_id}. Требуется повторная авторизация.")
                from app.database import delete_user_token
                delete_user_token(vk_user_id)
                raise ValueError(f"Токен пользователя {vk_user_id} истёк и не может быть обновлён.")
            
            db_token = get_user_token(vk_user_id)
            
            if not db_token:
                raise ValueError(f"Токен пользователя {vk_user_id} не найден после обновления")

        return db_token.access_token

    def _refresh_user_token(self, vk_user_id: int, refresh_token: str) -> bool:
        """
        Обновляет access_token с помощью refresh_token через VK OAuth API.
        """
        app_id = settings.vk_client_id
        app_secret = settings.vk_client_secret

        if not app_id or not app_secret:
            logger.error("❌ Для обновления токенов необходимы VK_CLIENT_ID и VK_CLIENT_SECRET в файле .env")
            return False

        try:
            response = requests.post(
                "https://oauth.vk.com/access_token",
                data={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token
                },
                timeout=15
            ).json()

            if "error" in response:
                logger.error(f"❌ Ошибка обновления токена: {response.get('error')} - {response.get('error_description')}")
                return False

            new_access_token = response["access_token"]
            new_refresh_token = response.get("refresh_token", refresh_token)
            expires_in = response.get("expires_in", 86400)
            
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            success = save_user_token(vk_user_id, new_access_token, new_refresh_token, expires_at)
            
            if success:
                logger.info(f"✅ Токен пользователя {vk_user_id} успешно обновлён!")
            
            return success

        except Exception as e:
            logger.error(f"❌ Исключение при обновлении токена: {e}")
            return False

    # 🔹 ВОТ ЭТОТ МЕТОД БЫЛ ПРОПУЩЕН РАНЕЕ — ДОБАВЛЯЕМ ЕГО СЕЙЧАС
    def exchange_code_for_token(self, vk_user_id: int, code: str, code_verifier: str, device_id: str) -> bool:
        """
        Обменивает код на токены используя PKCE и device_id из ответа VK.
        """
        app_id = settings.vk_client_id
        app_secret = settings.vk_client_secret

        try:
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
            ).json()

            if "error" in response:
                logger.error(f"❌ Ошибка обмена кода на токен: {response.get('error')} - {response.get('error_description')}")
                return False

            access_token = response["access_token"]
            refresh_token = response.get("refresh_token", "")
            expires_in = response.get("expires_in", 86400)
            returned_user_id = response.get("user_id")

            if returned_user_id and returned_user_id != vk_user_id:
                logger.warning(f"⚠️ ID в токене ({returned_user_id}) не совпадает с ID пользователя ({vk_user_id})")

            logger.info(f"✅ Успешно получен токен для пользователя {vk_user_id}")
            return self.save_new_token(vk_user_id, access_token, refresh_token, expires_in)

        except Exception as e:
            logger.error(f"❌ Исключение при обмене кода: {e}")
            return False

    def save_new_token(self, vk_user_id: int, access_token: str, refresh_token: str, expires_in_seconds: int) -> bool:
        """
        Сохраняет новый токен после первичной авторизации пользователя.
        """
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        return save_user_token(vk_user_id, access_token, refresh_token, expires_at)

    def start_background_refresh(self):
        """
        Заглушка для обратной совместимости.
        """
        logger.info("ℹ️ Фоновое обновление токенов теперь происходит автоматически при каждом запросе")
# Глобальный экземпляр для импорта в других модулях
token_manager = TokenManager()