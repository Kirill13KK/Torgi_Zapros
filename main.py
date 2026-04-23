import asyncio
import logging
import sys

from aiogram.types import BotCommand
from pythonjsonlogger import jsonlogger

from config.settings import get_settings
from core.runner import Runner
from core.state import State
from tg.bot import build_bot, build_dispatcher


BOT_COMMANDS: list[BotCommand] = [
    BotCommand(command="run", description="Непризнанные: боевой запуск"),
    BotCommand(command="run_zalog", description="Залоги: боевой запуск"),
    BotCommand(command="run_sobr", description="Собрания: боевой запуск"),
    BotCommand(command="dry_run", description="Непризнанные: тест"),
    BotCommand(command="dry_zalog", description="Залоги: тест"),
    BotCommand(command="dry_sobr", description="Собрания: тест"),
    BotCommand(command="clear_row", description="Сбросить окно по строке"),
    BotCommand(command="clear_partner", description="Сбросить окно по партнёру"),
    BotCommand(command="status", description="Последний запуск"),
    BotCommand(command="help", description="Подсказка по командам"),
]


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("main")

    state = State(settings.state_db_path)
    bot = build_bot(settings)
    runner = Runner(settings, state, bot)
    dp = build_dispatcher(settings, runner, state)

    try:
        await bot.set_my_commands(BOT_COMMANDS)
        log.info("set_my_commands ok")
    except Exception:
        log.exception("failed to set bot commands")

    log.info("bot started; автозапуск отключён, работает только по командам")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
