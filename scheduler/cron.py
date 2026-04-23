import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import Settings
from core.mutex import RunnerBusyError
from core.runner import Runner

log = logging.getLogger(__name__)


def build_scheduler(settings: Settings, runner: Runner) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=settings.timezone)

    async def _tick():
        try:
            summary = await runner.run(mode="live", triggered_by="scheduler")
            log.info("scheduled run done: %s", summary.format())
            if settings.service_chat_id:
                try:
                    await runner.bot.send_message(settings.service_chat_id, summary.format())
                except Exception:
                    log.exception("failed to post summary to service chat")
        except RunnerBusyError:
            log.warning("scheduled tick skipped: runner busy")

    trigger = CronTrigger(
        day_of_week=settings.cron_day_of_week,
        hour=settings.cron_hour,
        minute=settings.cron_minute,
        timezone=settings.timezone,
    )
    sched.add_job(_tick, trigger, id="weekly-run", replace_existing=True)
    return sched
