# ChronicaCare – Telegram Health Companion

ChronicaCare — «умный» Telegram-ассистент, который помогает не забывать о лекарствах, следить за запасами и держать здоровье в фокусе без дополнительных приложений. Всё происходит прямо в чате: от онбординга и карточек препаратов до напоминаний и статистики.

## Возможности

- **Онбординг и профиль.** Пользователь задаёт имя, часовой пояс (геолокацией или названием города), выбирает «личность» бота. Профиль редактируется через `/profile`.
- **Карточки лекарств.** Встроенный WebApp (`/add_med`) собирает название, дозировку, форму, остатки и заметки. Фото можно прикрепить: отправьте упаковку боту, он вернёт `file_id` и его можно вставить в форму.
- **Напоминания.** `/set_reminder` поддерживает фиксированное время, расписание по дням недели, интервалы, события («После завтрака +30») и геолокацию. Есть быстрые кнопки времени и режим “назойливых” уведомлений.
- **Учёт доз и запасов.** После подтверждения приёма бот списывает дозу и следит за остатками. При критическом уровне предлагает найти аптеку или зафиксировать задачу “позвонить врачу”.
- **Статистика и достижения.** `/stats` строит графики соблюдения режима, `/achievements` награждает за дисциплину. `/export` выгружает данные в JSON/CSV для врача.
- **Трекеры состояния.** `/symptom`, `/mood`, `/water` помогают вести дневники самочувствия.

## Технологии

- Python 3.11  
- [python-telegram-bot 20.x](https://docs.python-telegram-bot.org/)  
- FastAPI + Uvicorn для WebApp  
- SQLAlchemy + PostgreSQL (Railway)  
- APScheduler / JobQueue для фоновых задач  

## Локальный запуск

```bash
git clone https://github.com/RomaFka28/telegram-bot.git
cd telegram-bot
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

Создайте `.env`:

```
TELEGRAM_TOKEN=ваш_токен
WEB_APP_URL=http://localhost:8000
DATABASE_URL=postgresql://postgres:password@localhost:5432/chronica
```

Далее:

```bash
python -m compileall .
python main.py
```

WebApp:

```bash
uvicorn web_server:app --host 0.0.0.0 --port 8000
```

## Деплой на Railway

1. Создайте PostgreSQL-инстанс, сохраните `DATABASE_URL`.
2. Поднимите сервис **bot** из GitHub. Задайте `TELEGRAM_TOKEN`, `DATABASE_URL`, временно `WEB_APP_URL`.
3. Поднимите сервис **web** (команда `uvicorn web_server:app --host 0.0.0.0 --port $PORT`), включите Public Networking и возьмите домен `https://web-production-xxxx.up.railway.app`.
4. В сервисе бота обновите `WEB_APP_URL` на полученный домен и сделайте redeploy.

## Структура

- `main.py` — точка входа, регистрация команд, JobQueue.
- `handlers/` — онбординг, профиль, лекарства, напоминания, статистика, lifestyle.
- `services/` — работа с БД и доменной логикой.
- `models.py` — ORM-модели SQLAlchemy.
- `web/` — фронтенд WebApp.

## О боте

- **Название:** ChronicaCare  
- **Краткое описание:** «ChronicaCare напоминает о лекарствах, следит за запасами и ведёт твой ритм здоровья прямо в Telegram. Нажми /start, чтобы настроиться».
