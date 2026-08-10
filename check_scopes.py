# check_scopes.py
import vk_api
import os
from dotenv import load_dotenv

load_dotenv()

# Берем именно тот токен, который использует бот
token = os.getenv("VK_ACCESS_TOKEN")
group_id = os.getenv("VK_GROUP_ID")

print(f"Проверяем токен для группы {group_id}...")

vk_session = vk_api.VkApi(token=token)
api = vk_session.get_api()

# 1. Проверяем базовое право (должно работать)
try:
    user = api.users.get()[0]
    print(f"✅ users.get работает. Пользователь: {user['first_name']}")
except Exception as e:
    print(f"❌ users.get не работает: {e}")

# 2. Проверяем право groups (именно оно нужно для Long Poll)
try:
    group = api.groups.getById(group_id=group_id)[0]
    print(f"✅ groups.getById работает! Группа: {group['name']}")
    print("🎉 Право 'groups' ЕСТЬ в токене. Проблема в настройках Long Poll.")
except vk_api.exceptions.ApiError as e:
    if e.code == 15:
        print("❌ ОШИБКА 15: Право 'groups' ОТСУТСТВУЕТ в токене!")
        print("👉 Это значит, что VK не одобрил это право для вашего приложения, или оно слетело при генерации.")
    else:
        print(f"❌ Другая ошибка API: {e}")