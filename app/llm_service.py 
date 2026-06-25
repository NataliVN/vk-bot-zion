from __future__ import annotations

def build_prompt(child_name: str, child_age: int, event_date: str, fact: str, photos_count: int) -> str:
    return f"""
Ты SMM-редактор детской VR-арены.

Напиши нативный VK-пост на русском языке:
- поздравь ребенка с днем рождения;
- упомяни, что праздник прошел у нас;
- добавь интересный факт;
- мягко пригласи отметить день рождения у нас;
- без агрессивной рекламы и штампов;
- теплый, живой, дружелюбный тон;
- 700-1100 знаков;
- без хэштегов;
- верни только готовый текст.

Данные:
Имя ребенка: {child_name}
Возраст: {child_age}
Дата мероприятия: {event_date}
Интересный факт: {fact}
Количество фото: {photos_count}
""".strip()

def generate_post(child_name: str, child_age: int, event_date: str, fact: str, photos_count: int, chat_with_llm) -> str:
    return chat_with_llm(build_prompt(child_name, child_age, event_date, fact, photos_count), history=[])
