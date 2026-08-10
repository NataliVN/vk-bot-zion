# check_user_token.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Проверяем оба возможных названия переменной, которые могли быть в .env
token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_ACCESS_TOKEN")
group_id = os.getenv("VK_GROUP_ID", "0")

if not token:
    print("❌ Ошибка: Токен не найден в файле .env")
    print("💡 Убедитесь, что там есть строка VK_USER_TOKEN=... или VK_ACCESS_TOKEN=...")
    exit(1)

print(f"🔍 Проверяем токен: {token[:15]}...")
print("="*60)

# 1. Проверка жизнеспособности токена (базовый запрос)
resp_users = requests.post(
    "https://api.vk.com/method/users.get",
    params={"access_token": token, "v": "5.199"}
).json()

if "response" in resp_users:
    user_name = resp_users["response"][0].get("first_name", "Неизвестно")
    print(f"✅ ШАГ 1: Токен ЖИВОЙ! Владелец: {user_name}")
    
    # 2. Проверка наличия права 'groups' (критично для нашей задачи)
    resp_groups = requests.post(
        "https://api.vk.com/method/groups.getById",
        params={"access_token": token, "group_id": group_id, "v": "5.199"}
    ).json()
    
    if "response" in resp_groups:
        group_name = resp_groups["response"][0].get("name", "Неизвестно")
        print(f"✅ ШАГ 2: Право 'groups' ЕСТЬ. Группа: {group_name}")
        print("\n🎉 ОТЛИЧНЫЕ НОВОСТИ: Токен полностью готов к использованию для загрузки фото!")
    else:
        error = resp_groups.get("error", {})
        print(f"⚠️ ШАГ 2: Право 'groups' ОТСУТСТВУЕТ или есть ошибка.")
        print(f"   Код: {error.get('error_code')}, Сообщение: {error.get('error_msg')}")
        print("\n💡 ДЕЙСТВИЕ: Токен рабочий, но при его получении в scope не было указано 'groups'. Нужно получить токен заново.")
else:
    error = resp_users.get("error", {})
    print(f"❌ Токен НЕВАЛИДЕН или ПРОТУХ!")
    print(f"   Код ошибки: {error.get('error_code')}")
    print(f"   Сообщение: {error.get('error_msg')}")
    
    if error.get("error_code") == 5:
        print("\n💡 ДЕЙСТВИЕ: Токен протух или отозван. Нужно запустить vk_auth_helper.py и получить новый.")
    elif error.get("error_code") == 10:
        print("\n💡 ДЕЙСТВИЕ: Временная ошибка серверов VK (синхронизация). Подождите 5 минут и запустите скрипт снова.")
    else:
        print("\n💡 ДЕЙСТВИЕ: Проверьте, правильно ли скопирован токен в .env (без лишних пробелов).")

print("="*60)