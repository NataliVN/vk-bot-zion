# app/token_manager.py
import time
import requests
import logging
import os
import threading
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class TokenManager:
    def __init__(self):
        # Принудительно перечитываем .env при инициализации
        load_dotenv(override=True)
        self.client_id = os.getenv("VK_CLIENT_ID", "")
        self.client_secret = os.getenv("VK_CLIENT_SECRET", "")
        
    def get_valid_token(self) -> str:
        """Возвращает валидный User Token, обновляя его при необходимости"""
        load_dotenv(override=True)
        
        token = os.getenv("VK_USER_TOKEN", "")
        expires_at_str = os.getenv("VK_TOKEN_EXPIRES_AT", "0")
        
        try:
            expires_at = int(expires_at_str)
        except ValueError:
            expires_at = 0
            
        current_time = int(time.time())
        
        # Если токен истечет через 5 минут (300 сек) или уже истек - обновляем
        if expires_at - current_time < 300:
            logger.info("⏰ Токен скоро истечет или уже истек. Обновляем...")
            refresh_token = os.getenv("VK_REFRESH_TOKEN", "")
            device_id = os.getenv("VK_DEVICE_ID", "")
            code_verifier = os.getenv("VK_CODE_VERIFIER", "")
            
            new_token = self._refresh_token(refresh_token, device_id, code_verifier)
            if new_token:
                return new_token
            else:
                return token
        
        logger.info(f"✅ Токен валиден. Истекает через {(expires_at - current_time) // 60} минут.")
        return token
    
    def _refresh_token(self, refresh_token: str, device_id: str, code_verifier: str) -> str:
        """Обновляет токен через refresh_token"""
        if not all([refresh_token, device_id, code_verifier, self.client_id, self.client_secret]):
            logger.error("❌ Недостаточно данных для обновления токена. Проверьте VK_CLIENT_ID и VK_CLIENT_SECRET в .env")
            return ""
        
        try:
            token_url = "https://id.vk.com/oauth2/auth"
            payload = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'device_id': device_id,
                'code_verifier': code_verifier,
            }
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = requests.post(token_url, data=payload, headers=headers)
            data = response.json()
            
            if "access_token" in data:
                new_token = data['access_token']
                new_refresh_token = data.get('refresh_token', refresh_token)
                expires_in = data.get('expires_in', 3600)
                expires_at = int(time.time()) + expires_in
                
                env_file = ".env"
                
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                new_lines = []
                for line in lines:
                    if not any(line.startswith(prefix) for prefix in [
                        "VK_USER_TOKEN=", "VK_REFRESH_TOKEN=", "VK_TOKEN_EXPIRES_AT="
                    ]):
                        new_lines.append(line)
                
                new_lines.append(f"VK_USER_TOKEN={new_token}\n")
                new_lines.append(f"VK_REFRESH_TOKEN={new_refresh_token}\n")
                new_lines.append(f"VK_TOKEN_EXPIRES_AT={expires_at}\n")
                
                with open(env_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                
                load_dotenv(override=True)
                
                logger.info(f"✅ Токен успешно обновлен! Следующее обновление через {expires_in // 60} минут.")
                return new_token
            else:
                logger.error(f"❌ Ошибка обновления токена: {data}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Исключение при обновлении токена: {e}")
            return ""

    def force_refresh_if_needed(self) -> bool:
        """Принудительно обновляет токен, если до истечения меньше 6 дней.
        Вызывается фоновым потоком раз в неделю."""
        load_dotenv(override=True)
        
        expires_at_str = os.getenv("VK_TOKEN_EXPIRES_AT", "0")
        try:
            expires_at = int(expires_at_str)
        except ValueError:
            expires_at = 0
        
        current_time = int(time.time())
        six_days = 6 * 24 * 60 * 60  # 6 дней в секундах
        
        if expires_at - current_time < six_days:
            logger.info("🔄 [Фоновое обновление] Токен скоро истечет, обновляем...")
            refresh_token = os.getenv("VK_REFRESH_TOKEN", "")
            device_id = os.getenv("VK_DEVICE_ID", "")
            code_verifier = os.getenv("VK_CODE_VERIFIER", "")
            
            new_token = self._refresh_token(refresh_token, device_id, code_verifier)
            return bool(new_token)
        else:
            days_left = (expires_at - current_time) // (24 * 60 * 60)
            logger.info(f"✅ [Фоновое обновление] Токен валиден еще {days_left} дней, обновление не требуется.")
            return True


# Глобальный менеджер токенов (ТОЛЬКО ОДИН РАЗ!)
token_manager = TokenManager()


def start_background_refresh(interval_days: int = 7):
    """Запускает фоновый поток для периодического обновления токена."""
    interval_seconds = interval_days * 24 * 60 * 60
    
    def _refresh_loop():
        logger.info(f"🔁 Фоновое обновление токена запущено (раз в {interval_days} дней)")
        while True:
            time.sleep(interval_seconds)
            try:
                success = token_manager.force_refresh_if_needed()
                if success:
                    logger.info("✅ [Фон] Токен успешно обновлен в фоновом режиме")
                else:
                    logger.warning("⚠️ [Фон] Не удалось обновить токен в фоновом режиме")
            except Exception as e:
                logger.error(f"❌ [Фон] Ошибка фонового обновления: {e}")
    
    # daemon=True означает, что поток завершится автоматически при закрытии основного бота
    thread = threading.Thread(target=_refresh_loop, daemon=True)
    thread.start()
    return thread