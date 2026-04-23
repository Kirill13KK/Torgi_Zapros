from aiogram import Bot, Dispatcher

from config.settings import Settings
from core.runner import Runner
from core.state import State
from tg.handlers import build_router
from tg.middlewares import AdminOnly


def build_bot(settings: Settings) -> Bot:
    return Bot(token=settings.tg_bot_token)


def build_dispatcher(settings: Settings, runner: Runner, state: State) -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(AdminOnly(settings.admin_user_ids))
    dp.include_router(build_router(runner, state, settings))
    return dp
