"""One-shot CLI runner for local testing: `python cli.py --dry` or `python cli.py --live`."""
import asyncio
import logging
import sys

from config.settings import get_settings
from core.runner import Runner
from core.state import State
from tg.bot import build_bot


async def main() -> None:
    mode = "dry" if "--dry" in sys.argv else ("live" if "--live" in sys.argv else "dry")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    state = State(settings.state_db_path)
    bot = build_bot(settings)
    runner = Runner(settings, state, bot)
    try:
        summary = await runner.run(mode=mode, triggered_by="cli")
        print("\n" + summary.format())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
