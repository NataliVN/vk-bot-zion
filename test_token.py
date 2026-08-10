import vk_api
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("VK_ACCESS_TOKEN")
group_id = os.getenv("VK_GROUP_ID")

print(f"Проверяем токен для группы {group_id}...")

vk_session = vk_api.VkApi(token=token)
api = vk_session.get_api()

try:
    # Простой запрос, который требует прав 'groups'
    group_info = api.groups.getById(group_id=group_id)
    print(f"✅ УСПЕХ! Токен рабочий. Группа: {group_info[0]['name']}")
except vk_api.exceptions.ApiError as e:
    print(f"❌ ОШИБКА API: {e}")
except Exception as e:
    print(f"❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")