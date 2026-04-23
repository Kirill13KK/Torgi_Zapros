# Torgi bot — еженедельный запросник по непризнанным торгам

Бот читает вкладку «Непризнанные» в гугл-таблице и раз в 7 дней шлёт партнёрам в TG шаблонный запрос по каждой строке без «признака готовности» (любая заливка в столбце H).

## Что надо сделать ПЕРЕД запуском (блокеры)

1. Положить JSON сервисного аккаунта в `credentials/google.json`.
2. Расшарить гугл-таблицу (ID `1JLm_Q2lEfyFc45wLQGqPkq3ET_W_e0Vhyi0vWilbVuM`) сервиснику `torgi-aspb-api@principal-storm-493916-j9.iam.gserviceaccount.com` (Редактор достаточен).
3. В таблице создать вкладку **`Партнёры`** с колонками:
   - A: `name` (точно как в основной вкладке)
   - B: `chat_id` (число, ID TG-группы: отрицательный, начинается с `-100`)
4. Добавить бота в каждую группу партнёра и дать права писать.
5. Получить `chat_id` служебного чата (бот → group → посмотреть в логах updates или через @getmyid_bot) + `user_id` Димы для whitelist.
6. Скопировать `.env.example` → `.env` и заполнить:
   - `SERVICE_CHAT_ID` — служебный чат
   - `ADMIN_USER_IDS` — через запятую
   - `COL_PARTNER` — буква столбца с названием партнёра (сейчас заглушка `A`)
   - `COL_FIO` — буква столбца с ФИО (сейчас заглушка `B`)
   - `TYPE_REALTY_VALUES` / `TYPE_VEHICLE_VALUES` / `TYPE_WEAPON_VALUES` — реальные строки из столбца F

## Локальный запуск (dev)

```
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # отредактировать
python main.py
```

В TG служебном чате:
- `/dry_run` — прогон без отправок
- `/run` — боевой запуск
- `/status` — последний запуск

## Деплой на VPS (Ubuntu/Debian)

```
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
sudo mkdir -p /opt/torgi-bot && sudo chown $USER /opt/torgi-bot
cd /opt/torgi-bot
git clone <repo-url> .          # или залить rsync/scp
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
# положить credentials/google.json и .env
```

Systemd unit `/etc/systemd/system/torgi-bot.service`:

```
[Unit]
Description=Torgi TG bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/torgi-bot
ExecStart=/opt/torgi-bot/.venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now torgi-bot
sudo journalctl -u torgi-bot -f
```

## Структура проекта

```
config/settings.py    pydantic-settings, .env
templates/messages.py 3 шаблона (raw strings, по ТЗ v1.1 п.1.4)
sheets/               Google Sheets клиент + парсер вкладок
core/runner.py        пайплайн dry/live
core/state.py         SQLite: runs, sends, last_success
core/mutex.py         portalocker (запрет параллельных запусков, п.1.3 v1.1)
core/retry.py         5s/30s, max 2 (п.2.2 v1.1)
tg/                   aiogram bot + admin middleware (п.1.1 v1.1)
scheduler/cron.py     APScheduler еженедельный триггер
main.py               entrypoint
```

## Что НЕ входит в MVP (п.2.3 v1.1)

- Веб-админка
- Мультиязычность
- Авто-определение типа имущества по названию
- CRM-интеграция
- Массовые рассылки вне таблицы
- Отправка по @username
- Разные оттенки зелёного — учитываем любую заливку
