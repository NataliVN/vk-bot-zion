# VK Birthday Bot

Бот для сотрудников: собирает фото и данные, генерирует поздравление, показывает черновик на модерацию и ставит отложенный пост в VK.

## Запуск
1. Создайте `.env`
2. Установите зависимости:
   pip install -r requirements.txt
3. Запустите:
   python -m app.bot

## Что нужно включить в VK
- Сообщения сообщества
- Bots Long Poll API
- Callback buttons / inline keyboard
- Права токена: messages, photos, wall, groups
