# check_permissions.py
import vk_api
import os
from dotenv import load_dotenv

load_dotenv()

# Добавляем fallback "", чтобы тип всегда был str, а не str | None
token = os.getenv("VK_GROUP_TOKEN") or os.getenv("VK_ACCESS_TOKEN") or ""
group_id_str = os.getenv("VK_GROUP_ID") or "0"

print(f"🔍 Проверяем права токена для группы {group_id_str}...")
print("="*70)

vk_session = vk_api.VkApi(token=token)
api = vk_session.get_api()

# Безопасное преобразование в int
try:
    group_id = int(group_id_str)
except ValueError:
    print("❌ Ошибка: VK_GROUP_ID в файле .env не является числом!")
    exit(1)


def test_scope(scope_name: str, test_func) -> None:
    """Тестирует конкретное право и выводит результат"""
    try:
        test_func()
        print(f"✅ {scope_name.upper():15} - ЕСТЬ")
    except vk_api.exceptions.ApiError as e:
        if e.code == 15:
            print(f"❌ {scope_name.upper():15} - НЕТ (ошибка 15: Access denied)")
        elif e.code == 10:
            print(f"⚠️ {scope_name.upper():15} - ОШИБКА 10 (Токен отвергнут шлюзом VK)")
        elif e.code in [901, 100]:  # 901 - спам, 100 - неверный параметр, но право есть
            print(f"✅ {scope_name.upper():15} - ЕСТЬ (метод сработал, но заблокирован антиспамом/параметрами)")
        else:
            print(f"⚠️ {scope_name.upper():15} - Ошибка {e.code}")
    except Exception as e:
        print(f"❓ {scope_name.upper():15} - Неизвестная ошибка: {e}")


# 🔹 Тестируем каждое право через прямой вызов метода API
test_scope("messages", lambda: api.messages.send(peer_id=1, message="test", random_id=0))
test_scope("wall", lambda: api.wall.post(owner_id=-group_id, message="test", from_group=1))
test_scope("photos", lambda: api.photos.getWallUploadServer(group_id=group_id))
test_scope("groups", lambda: api.groups.getById(group_id=group_id))

print("="*70)