# check_strict.py
import os
import requests
from dotenv import load_dotenv

# 1. ПРИНУДИТЕЛЬНО перечитываем .env, перезаписывая любые кэши
load_dotenv(override=True)

print("🔍 ШАГ 1: Читаем файл .env вручную (что там написано на самом деле):")
print("-" * 60)
with open(".env", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and ("VK_" in line or "YA_" in line):
            parts = line.split("=", 1)
            if len(parts) == 2:
                key, val = parts
                # Показываем первые 25 символов, чтобы понять, какой это токен
                display_val = val[:25] + "..." if len(val) > 25 else val
                print(f"   {key:20} = {display_val}")

print("\n" + "="*60)
print("🔍 ШАГ 2: Что видит Python через os.getenv:")
print("-" * 60)

user_token = os.getenv("VK_USER_TOKEN")
access_token = os.getenv("VK_ACCESS_TOKEN")
group_id = os.getenv("VK_GROUP_ID", "0")

print(f"   VK_USER_TOKEN:   {user_token[:25] + '...' if user_token else 'None'}")
print(f"   VK_ACCESS_TOKEN: {access_token[:25] + '...' if access_token else 'None'}")
print(f"   VK_GROUP_ID:     {group_id}")
print("="*60)

# Выбираем токен для проверки. Приоритет у VK_USER_TOKEN.
token = user_token if user_token else access_token

if not token:
    print("\n❌ ОШИБКА: Ни один токен не найден!")
    exit(1)

print(f"\n🚀 ПРОВЕРЯЕМ ТОКЕН: {token[:15]}...")

# Проверка users.get
resp_users = requests.post(
    "https://api.vk.com/method/users.get",
    params={"access_token": token, "v": "5.199"}
).json()

if "response" in resp_users:
    user_name = resp_users["response"][0].get("first_name", "Неизвестно")
    print(f"✅ ШАГ 3: Токен ЖИВОЙ! Владелец: {user_name}")
    
    # Проверка groups
    resp_groups = requests.post(
        "https://api.vk.com/method/groups.getById",
        params={"access_token": token, "group_id": group_id, "v": "5.199"}
    ).json()
    
    if "response" in resp_groups:
        group_name = resp_groups["response"][0].get("name", "Неизвестно")
        print(f"✅ ШАГ 4: Право 'groups' ЕСТЬ. Группа: {group_name}")
        print("\n🎉 ОТЛИЧНЫЕ НОВОСТИ: Токен полностью готов!")
    else:
        error = resp_groups.get("error", {})
        print(f"⚠️ ШАГ 4: Ошибка прав. Код: {error.get('error_code')}, Сообщение: {error.get('error_msg')}")
else:
    error = resp_users.get("error", {})
    print(f"❌ Токен НЕВАЛИДЕН или ПРОТУХ!")
    print(f"   Код ошибки: {error.get('error_code')}, Сообщение: {error.get('error_msg')}")