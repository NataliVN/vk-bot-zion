# app/token_manager.py
import os
import time
import logging
import requests
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)

class VKTokenManager:
    def __init__(self, vk_session):
        load_dotenv()
        self.client_id = os.getenv("VK_CLIENT_ID")
        self.client_secret = os.getenv("VK_CLIENT_SECRET")
        self.access_token = os.getenv("VK_ACCESS_TOKEN")
        self.refresh_token = os.getenv("VK_REFRESH_TOKEN")
        self.expires_at = int(os.getenv("VK_TOKEN_EXPIRES_AT", 0))
        
        # Сохраняем ссылку на активную сессию vk_api, чтобы обновлять токен "на лету"
        self.vk_session = vk_session

    def is_expired(self) -> bool:
        # Обновляем токен за 5 минут (300 сек) до реального истечения, чтобы избежать сбоев
        return time.time() >= (self.expires_at - 300)

    def refresh(self) -> bool:
        logger.info("⚠️ Токен истекает или истек. Запуск процесса обновления...")
        
        url = "https://id.vk.com/oauth2/auth"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            response = requests.post(url, data=payload)
            data = response.json()

            if "access_token" in data:
                self.access_token = data["access_token"]
                # VK часто выдает новый refresh_token при обновлении (ротация)
                self.refresh_token = data.get("refresh_token", self.refresh_token)
                expires_in = data.get("expires_in", 3600)
                self.expires_at = int(time.time()) + expires_in

                # 1. Обновляем файл .env
                env_path = ".env"
                set_key(env_path, "VK_ACCESS_TOKEN", self.access_token)
                set_key(env_path, "VK_REFRESH_TOKEN", self.refresh_token)
                set_key(env_path, "VK_TOKEN_EXPIRES_AT", str(self.expires_at))
                
                # 2. Обновляем токен в активной сессии vk_api, чтобы бот не перезапускался
                if self.vk_session:
                    self.vk_session.token["access_token"] = self.access_token

                logger.info(f"✅ Токен успешно обновлен! Следующее обновление через {expires_in} сек.")
                return True
            else:
                logger.error(f"❌ Ошибка обновления токена: {data}")
                return False

        except Exception as e:
            logger.exception(f"❌ Исключение при обновлении токена: {e}")
            return False

    def get_valid_token(self) -> str:
        if self.is_expired():
            self.refresh()
        
        # 🔹 Явная проверка для анализатора типов и безопасности
        if self.access_token is None:
            raise ValueError("Критическая ошибка: VK_ACCESS_TOKEN не найден в файле .env!")
            
        return self.access_token