# vk_auth_helper.py
import secrets
import hashlib
import base64
import requests
import time
import re
from urllib.parse import urlparse, parse_qs
from dotenv import set_key, load_dotenv

# 🔹 ВСТАВЬТЕ СЮДА ВАШИ ДАННЫЕ ИЗ dev.vk.com
CLIENT_ID = "54654494"          # Только цифры
CLIENT_SECRET = "ee0ca5a1ee0ca5a1ee0ca5a17eed4d53bfeee0cee0ca5a18432cf6fef48ce6d1d4c4b29"  # Длинная строка
def generate_pkce():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return code_verifier, code_challenge

def main():
    print("🔄 Генерация PKCE-параметров...")
    code_verifier, code_challenge = generate_pkce()
    
    auth_url = (
        f"https://id.vk.com/authorize?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&scope=photos,wall,messages,groups,offline,video"
        f"&redirect_uri=https://oauth.vk.com/blank.html"
        f"&state=12345"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    
    print("\n" + "="*70)
    print("📋 ШАГ 1: Скопируйте эту ссылку и откройте её в браузере:")
    print(auth_url)
    print("="*70)
    print("\n👉 Нажмите 'Разрешить' на странице VK.")
    print("👉 Скопируйте ВЕСЬ URL из адресной строки (начинается с https://oauth.vk.com/blank.html?code=...)")
    
    redirect_url = input("\n📥 Вставьте полный URL из адресной строки сюда и нажмите Enter:\n").strip()
    
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    
    if 'code' not in params or 'device_id' not in params:
        print("\n❌ ОШИБКА: В ссылке не найдены параметры 'code' или 'device_id'.")
        print("Убедитесь, что вы скопировали ссылку ПОСЛЕ нажатия кнопки 'Разрешить'.")
        return

    auth_code = params['code'][0]
    device_id = params['device_id'][0]
    
    print("\n🔄 ШАГ 2: Обмен кода на токены и запись в .env...")
    
    token_url = "https://id.vk.com/oauth2/auth"
    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': 'https://oauth.vk.com/blank.html',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'device_id': device_id,
        'code_verifier': code_verifier,
        'state': '12345'
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(token_url, data=payload, headers=headers)
    data = response.json()
    
    if "access_token" in data:
        print("✅ Токены получены от VK!")
        
        # 🔹 АВТОМАТИЧЕСКАЯ ЗАПИСЬ В .ENV
        env_file = ".env"
        # Записываем БЕЗ кавычек (quote_mode=None)
               # 🔹 АВТОМАТИЧЕСКАЯ ЗАПИСЬ В .ENV (БЕЗ КАВЫЧЕК!)
        env_file = ".env"
        set_key(env_file, "VK_USER_TOKEN", data['access_token'], quote_mode="never")
        set_key(env_file, "VK_REFRESH_TOKEN", data.get('refresh_token', ''), quote_mode="never")
        set_key(env_file, "VK_DEVICE_ID", device_id, quote_mode="never")
        set_key(env_file, "VK_CODE_VERIFIER", code_verifier, quote_mode="never")
        
        expires_at = int(time.time()) + data.get('expires_in', 3600)
        set_key(env_file, "VK_TOKEN_EXPIRES_AT", str(expires_at), quote_mode="never")

        print("✅ Токены успешно и чисто записаны в файл .env!")
        
        print("\n⚠️ ВАЖНО: Серверам VK требуется 3-5 минут на синхронизацию нового токена.")
        print("🛑 НЕ ЗАПУСКАЙТЕ БОТА ПРЯМО СЕЙЧАС. Подождите 5 минут.")
        print("Через 5 минут запустите: python check_user_token.py")
        print("Если токен живой - запускайте: python -m app.bot")
        
    else:
        print(f"\n❌ ОШИБКА при получении токенов: {data}")

if __name__ == "__main__":
    main()