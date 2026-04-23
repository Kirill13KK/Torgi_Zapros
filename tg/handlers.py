import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import Settings
from core.mutex import RunnerBusyError
from core.runner import Runner
from core.state import State

log = logging.getLogger(__name__)


HELP_TEXT = """Команды бота:

Боевой запуск (с отправкой):
  /run        — вкладка «Непризнанные»
  /run_zalog  — вкладка «Залоги»
  /run_sobr   — вкладка «Собрания»

Тестовый прогон (без отправки):
  /dry_run      — вкладка «Непризнанные»
  /dry_zalog    — вкладка «Залоги»
  /dry_sobr     — вкладка «Собрания»

Сброс окна (чтобы повторно отправить):
  /clear_row <источник> <row> <партнёр>
    пример: /clear_row sobr 40 Сизов
    источники: neprizn, zalog, sobr
  /clear_partner <партнёр>
    пример: /clear_partner Сизов
    сбрасывает всё по партнёру (и по вариантам имени)

Служебные:
  /status  — последний запуск и его итоги
  /help    — эта подсказка"""


SOURCE_ALIASES = {
    "neprizn": "Непризнанные",
    "nepriznannye": "Непризнанные",
    "непризнанные": "Непризнанные",
    "zalog": "Залоги",
    "zalogi": "Залоги",
    "залоги": "Залоги",
    "sobr": "Собрания",
    "sobrania": "Собрания",
    "собрания": "Собрания",
}


def _fmt_dt(iso: str | None, tz_name: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tz_name))
        return dt.strftime("%d.%m.%Y в %H:%M")
    except Exception:
        return iso


def build_router(runner: Runner, state: State, settings: Settings) -> Router:
    r = Router()

    async def _execute(msg: Message, mode: str, source_filter: set[str] | None, label: str) -> None:
        human = "боевой" if mode == "live" else "тестовый"
        await msg.answer(
            f"Запускаю {human} проход: {label}.\nПришлю сводку когда закончу."
        )
        try:
            summary = await runner.run(
                mode=mode,
                triggered_by=f"user:{msg.from_user.id}",
                source_filter=source_filter,
            )
        except RunnerBusyError:
            last = state.last_run()
            hint = f"\nПоследний запуск: {last['run_id']} ({last['mode']})" if last else ""
            await msg.answer("Обработка уже выполняется. Подожди завершения." + hint)
            return
        await msg.answer(summary.format())

    # боевой
    @r.message(Command("run"))
    async def run_neprizn(msg: Message) -> None:
        await _execute(msg, "live", {"Непризнанные"}, "«Непризнанные»")

    @r.message(Command("run_zalog"))
    async def run_zalog(msg: Message) -> None:
        await _execute(msg, "live", {"Залоги"}, "«Залоги»")

    @r.message(Command("run_sobr"))
    async def run_sobr(msg: Message) -> None:
        await _execute(msg, "live", {"Собрания"}, "«Собрания»")

    # тест
    @r.message(Command("dry_run"))
    async def dry_neprizn(msg: Message) -> None:
        await _execute(msg, "dry", {"Непризнанные"}, "«Непризнанные»")

    @r.message(Command("dry_zalog"))
    async def dry_zalog(msg: Message) -> None:
        await _execute(msg, "dry", {"Залоги"}, "«Залоги»")

    @r.message(Command("dry_sobr"))
    async def dry_sobr(msg: Message) -> None:
        await _execute(msg, "dry", {"Собрания"}, "«Собрания»")

    # сброс окна
    @r.message(Command("clear_row"))
    async def clear_row_cmd(msg: Message) -> None:
        parts = (msg.text or "").split(maxsplit=3)
        if len(parts) < 4:
            await msg.answer(
                "Использование: /clear_row <источник> <row> <партнёр>\n"
                "Пример: /clear_row sobr 40 Сизов\n"
                "Источники: neprizn, zalog, sobr"
            )
            return
        _, src_alias, row_str, partner = parts
        try:
            row_idx = int(row_str)
        except ValueError:
            await msg.answer(f"row должен быть числом, получено: {row_str!r}")
            return
        source_name = SOURCE_ALIASES.get(src_alias.lower())
        if not source_name:
            await msg.answer(
                f"Неизвестный источник: {src_alias!r}. Доступны: neprizn, zalog, sobr"
            )
            return
        deleted = state.clear_row_window(partner.strip(), source_name, row_idx)
        await msg.answer(
            f"Очищено записей: {deleted}\n"
            f"Источник: {source_name}\nRow: {row_idx}\nПартнёр: {partner.strip()}"
        )

    @r.message(Command("clear_partner"))
    async def clear_partner_cmd(msg: Message) -> None:
        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await msg.answer(
                "Использование: /clear_partner <партнёр>\n"
                "Пример: /clear_partner Сизов\n"
                "Очищает все записи окна по партнёру (и по вариантам имени)"
            )
            return
        substr = parts[1].strip()
        deleted, matched = state.clear_partner_window(substr)
        if not matched:
            await msg.answer(f"Не найдено отправок для партнёра содержащего {substr!r}")
            return
        names = "\n  • ".join(matched)
        await msg.answer(
            f"Очищено записей: {deleted}\n"
            f"Совпавшие имена:\n  • {names}"
        )

    # служебные
    @r.message(Command("help"))
    async def help_cmd(msg: Message) -> None:
        await msg.answer(HELP_TEXT)

    @r.message(Command("start"))
    async def start_cmd(msg: Message) -> None:
        await msg.answer("Привет, готов к работе.\n\n" + HELP_TEXT)

    @r.message(Command("status"))
    async def status_cmd(msg: Message) -> None:
        last = state.last_run()
        if not last:
            await msg.answer("Запусков ещё не было. Бот готов к работе.")
            return
        mode_ru = "боевой" if last["mode"] == "live" else "тестовый"
        started = _fmt_dt(last["started_at"], settings.timezone)
        finished = _fmt_dt(last["finished_at"], settings.timezone) if last["finished_at"] else "ещё идёт"
        lines = [
            "📋 Последний запуск",
            "",
            f"Режим: {mode_ru}",
            f"Начат:     {started}",
            f"Завершён:  {finished}",
        ]
        if last["finished_at"]:
            lines += [
                "",
                f"Всего строк:  {last['total']}",
                f"Отправлено:   {last['sent']}",
                f"Пропущено:    {last['skipped']}",
                f"Ошибок:       {last['errors']}",
            ]
        await msg.answer("\n".join(lines))

    return r
