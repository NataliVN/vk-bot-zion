# check_scopes.py
import os
import requests
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv(override=True)

user_token = os.getenv("VK_USER_TOKEN")
if not user_token:
    print("❌ Ошибка: VK_USER_TOKEN не найден в файле .env")
    exit(1)

print("🔍 Проверяем права токена через VK API...\n")

# Метод VK API для получения прав приложения
url = "https://api.vk.com/method/account.getAppPermissions"
params = {
    "access_token": user_token,
    "v": "5.199"
}

response = requests.get(url, params=params).json()

if "error" in response:
    print(f"❌ Ошибка VK API: {response['error']['error_msg']}")
    print("💡 Возможно, токен недействителен или отозван.")
else:
    mask = response["response"]
    print(f"🔢 Числовая маска прав: {mask}\n")
    print("📋 Расшифровка прав:")
    
    # Проверяем конкретные биты маски
    if mask & 4:
        print("  ✅ Фотографии (photos)")
    else:
        print("  ❌ Фотографии (photos)")
        
    if mask & 16:
        print("  ✅ Видеозаписи (video)")
    else:
        print("  ❌ Видеозаписи (video)  <-- ВОТ ПРИЧИНА!")
        
    if mask & 131072:
        print("  ✅ Стена (wall)")
    else:
        print("  ❌ Стена (wall)")
        
    if mask & 8388608:
        print("  ✅ Сообщения (messages)")
    else:
        print("  ❌ Сообщения (messages)")

    print("\n💡 Если напротив 'Видеозаписи' стоит ❌, значит токен был получен без галочки 'Доступ к видеозаписям'.")