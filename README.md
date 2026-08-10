# 🤖 VR Zion VK Bot

Бот для автоматического создания отложенных постов в сообществе VK для арены виртуальной реальности **VR Zion** (г. Тула, ул. Тургеневская 69Б).

## ✨ Возможности

- 🎂 **Пост про день рождения** — бот собирает данные (имя, возраст, дата, факт) и генерирует поздравление через Yandex GPT
- ✍️ **Свободный пост** — создание любого поста по описанию от оператора
- 📅 **Выбор времени публикации** — вручную (ДД.ММ ЧЧ:ММ) или кнопкой "Завтра"
- 📸 **Загрузка медиа** — поддержка JPG, PNG, HEIC (автоконтвертация), MP4, MOV
- 📦 **Пакетная загрузка** — можно отправлять несколько файлов сразу
- 🔁 **Автообновление токенов** — бот работает 24/7 без ручного вмешательства
- 👥 **Уведомления операторам** — все созданные посты автоматически анонсируются
- 🛡 **Белый список пользователей** — доступ только для авторизованных сотрудников

---

## 📁 Структура проекта

```
vk-bot-zion/
├── app/
│   ├── bot.py                  # Точка входа, цикл Long Poll
│   ├── config.py               # Загрузка настроек из .env
│   ├── dialog.py               # Логика диалогов и загрузки медиа
│   ├── llm_service_yandex.py   # Интеграция с Yandex GPT
│   └── token_manager.py        # Автоматическое обновление токенов
├── prompts/
│   └── post_prompt.txt         # Шаблон промпта для постов про ДР
├── media/                      # Временная папка для загрузки фото
├── .env                        # Секреты и настройки (НЕ коммитить!)
├── .gitignore
├── requirements.txt            # Зависимости Python
├── vk_auth_helper.py           # Скрипт для получения User Token
└── README.md
```

---

## 🚀 Установка

### 1. Требования

- **Python 3.10 или выше** ([скачать](https://www.python.org/downloads/))
- **Git** (опционально, для клонирования)

### 2. Клонирование / копирование проекта

```bash
git clone <ваш-репозиторий>
cd vk-bot-zion
```

Или просто скопируйте папку на целевой компьютер.

### 3. Создание виртуального окружения

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Установка зависимостей

```bash
pip install -r requirements.txt
```

**Содержимое `requirements.txt`:**
```
vk-api
requests
python-dotenv
httpx
Pillow
pillow-heif
```

---

## 🔐 Настройка `.env`

Создайте файл `.env` в корне проекта со следующим содержимым:

```env
# === VK Community Token (вечный, из настроек группы) ===
VK_GROUP_TOKEN=vk1.a.ваш_ключ

# === VK User Token (обновляется автоматически) ===
VK_USER_TOKEN=vk2.a.ваш_ключ
VK_REFRESH_TOKEN=ваш_refresh_token
VK_TOKEN_EXPIRES_AT=1234567890
VK_DEVICE_ID=ваш_device_id
VK_CODE_VERIFIER=ваш_code_verifier

# === Данные приложения VK (для автообновления токена) ===
VK_CLIENT_ID=123456789
VK_CLIENT_SECRET=ваш_секретный_ключ

# === ID группы и пользователей ===
VK_GROUP_ID=219995441
ADMIN_USER_IDS=6510108,123456789
OPERATOR_USER_IDS=6510108,3912478

# === Yandex GPT ===
YA_API_KEY=ваш_api_key
YA_FOLDER_ID=ваш_folder_id

# === Прочее ===
UPLOAD_DIR=media
```

> ⚠️ **Важно:** Значения пишите **без кавычек**. ID через запятую **без пробелов**.

### Где взять токены и ID:

| Переменная | Где взять |
|---|---|
| `VK_GROUP_TOKEN` | Настройки сообщества → Работа с API → Создать ключ |
| `VK_CLIENT_ID` | [dev.vk.com](https://dev.vk.com) → ID приложения |
| `VK_CLIENT_SECRET` | Там же → Защищённый ключ |
| `VK_USER_TOKEN` и др. | Запустить `python vk_auth_helper.py` |
| `YA_API_KEY` | [Yandex Cloud](https://console.cloud.yandex.ru/) → Service Account → API-ключ |
| `YA_FOLDER_ID` | Там же → ID каталога |
| `ADMIN_USER_IDS` | VK ID сотрудников (через `vk.com/id123456`) |
| `OPERATOR_USER_IDS` | VK ID тех, кто получает уведомления |

---

## 🎟 Получение User Token (OAuth)

User Token живет **1 час**, но бот **автоматически** обновляет его через `refresh_token`. Вам нужно получить его только один раз.

### Пошаговая инструкция:

1. Активируйте виртуальное окружение:
   ```bash
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

2. Запустите скрипт авторизации:
   ```bash
   python vk_auth_helper.py
   ```

3. Скрипт выдаст ссылку — откройте её в браузере.

4. Войдите в VK и нажмите **"Разрешить"**.

5. После редиректа скопируйте **весь URL** из адресной строки (он будет длинным, начинается с `https://login.vk.com/?act=...`).

6. Вставьте URL в терминал и нажмите Enter.

7. Скрипт автоматически запишет все нужные значения в `.env`:
   - `VK_USER_TOKEN`
   - `VK_REFRESH_TOKEN`
   - `VK_TOKEN_EXPIRES_AT`
   - `VK_DEVICE_ID`
   - `VK_CODE_VERIFIER`

8. Готово! Бот будет сам обновлять токен раз в час.

---

## ▶️ Запуск бота

### Локально (для тестов)

```bash
python -m app.bot
```

Для остановки: `Ctrl+C`

---

## 🖥 Запуск в продакшене 24/7

### Вариант А: Windows (через NSSM)

**NSSM** (Non-Sucking Service Manager) — утилита для запуска Python-скриптов как службы Windows.

1. **Скачайте NSSM:** [nssm.cc/download](https://nssm.cc/download)

2. **Распакуйте** в любую папку (например, `C:\nssm\`).

3. **Установите службу** (запустите CMD от имени администратора):
   ```cmd
   C:\nssm\win64\nssm install VRZionBot
   ```

4. В открывшемся окне заполните:
   - **Path:** `C:\Python314\python.exe` (путь к вашему Python)
   - **Startup directory:** `C:\path\to\vk-bot-zion` (путь к проекту)
   - **Arguments:** `-m app.bot`

5. Перейдите на вкладку **"I/O"** и укажите файлы для логов:
   - Output: `C:\path\to\vk-bot-zion\logs\out.log`
   - Error: `C:\path\to\vk-bot-zion\logs\err.log`

6. Нажмите **"Install service"**.

7. **Управление службой:**
   ```cmd
   nssm start VRZionBot      # Запустить
   nssm stop VRZionBot       # Остановить
   nssm restart VRZionBot    # Перезапустить
   nssm edit VRZionBot       # Редактировать настройки
   nssm remove VRZionBot     # Удалить службу
   ```

8. Служба будет автоматически запускаться при старте Windows.

### Вариант Б: macOS (через launchd)

1. Создайте файл `~/Library/LaunchAgents/com.vrzion.bot.plist`:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.vrzion.bot</string>
       <key>ProgramArguments</key>
       <array>
           <string>/Users/natalia/Репозиторий/vk-bot-zion/.venv/bin/python</string>
           <string>-m</string>
           <string>app.bot</string>
       </array>
       <key>WorkingDirectory</key>
       <string>/Users/natalia/Репозиторий/vk-bot-zion</string>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/Users/natalia/Репозиторий/vk-bot-zion/logs/out.log</string>
       <key>StandardErrorPath</key>
       <string>/Users/natalia/Репозиторий/vk-bot-zion/logs/err.log</string>
   </dict>
   </plist>
   ```

2. Создайте папку для логов:
   ```bash
   mkdir -p logs
   ```

3. Загрузите службу:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.vrzion.bot.plist
   ```

4. Управление:
   ```bash
   launchctl stop com.vrzion.bot      # Остановить
   launchctl start com.vrzion.bot     # Запустить
   launchctl unload ~/Library/LaunchAgents/com.vrzion.bot.plist  # Выгрузить
   ```

### Вариант В: Linux (через systemd)

Создайте файл `/etc/systemd/system/vrzion-bot.service`:

```ini
[Unit]
Description=VR Zion VK Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/vk-bot-zion
ExecStart=/opt/vk-bot-zion/.venv/bin/python -m app.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl enable vrzion-bot
sudo systemctl start vrzion-bot
sudo systemctl status vrzion-bot
```

---

## 🔧 Обслуживание

### Автообновление токенов

Бот **сам** обновляет User Token:
- При каждом запросе на загрузку фото/создание поста
- Раз в 7 дней — фоновое обновление (чтобы `refresh_token` не протух)

Если `refresh_token` всё же протухнет (через несколько месяцев), бот пришлет уведомление админу в VK.

### Ручное обновление токена

Если бот перестал загружать фото или создавать посты:

```bash
python vk_auth_helper.py
# Пройдите авторизацию заново
python -m app.bot  # Перезапустите бота
```

### Логи

Логи пишутся в консоль. При запуске через NSSM/launchd/systemd — в файлы `logs/out.log` и `logs/err.log`.

Ключевые сообщения в логах:
- `✅ Токен валиден` — всё хорошо
- `⏰ Токен скоро истечет. Обновляем...` — штатное обновление
- `❌ Ошибка обновления токена` — нужно вручную запустить `vk_auth_helper.py`
- `📋 Получено вложений в пакете: N` — идет загрузка файлов
- `✅ Пост создан с ID: N` — пост опубликован

### Частые проблемы

| Проблема | Решение |
|---|---|
| `User authorization failed: invalid access_token` | Токен протух. Запустите `python vk_auth_helper.py` |
| `photo is undefined` | Проблема с кодировкой. Убедитесь, что используется `data=` вместо `params=` в `requests.post` |
| `session is compromised` | Использован один `refresh_token` дважды. Запустите `vk_auth_helper.py` заново |
| Бот не отвечает на сообщения | Проверьте `ADMIN_USER_IDS` в `.env` и перезапустите бота |
| HEIC не загружается | Установите `pillow-heif`: `pip install pillow-heif` |

---

## 🛡 Безопасность

- **Никогда не коммитьте `.env` в git!** Файл уже добавлен в `.gitignore`.
- **Храните `.env` в секрете** — там токены с полным доступом к вашему аккаунту VK.
- **Используйте `ADMIN_USER_IDS`** — только указанные ID могут создавать посты.
- **Регулярно проверяйте логи** на предмет подозрительной активности.

---

## 📝 Использование

1. Напишите боту в VK: `/start` или `старт`
2. Выберите тип поста:
   - 🎂 Пост про день рождения → введите 4 строки данных
   - ✍️ Свободный пост → опишите тему в свободной форме
3. Утвердите сгенерированный текст (или отредактируйте/перегенерируйте)
4. Укажите время публикации (или нажмите "Завтра")
5. Пришлите фото/видео (можно несколько сразу)
6. Нажмите "Готово к публикации"

Готово! Пост появится в сообществе в указанное время.

---

## 👨‍💻 Разработка

Автор: Natalia  
Дата создания: Август 2026  
Версия: 1.0

### Локальный запуск для разработки:

```bash
source .venv/bin/activate  # или .venv\Scripts\activate на Windows
python -m app.bot
```

---

**VR Zion** — арена виртуальной реальности в Туле  
🌐 [vr-zion.ru](https://vr-zion.ru)  
📍 г. Тула, ул. Тургеневская 69Б