import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from googleapiclient.errors import HttpError

from config.settings import DataSource, Settings
from core.mutex import RunnerBusyError, acquire_runner_lock
from core.retry import retry_async
from core.state import State
from sheets.client import SheetsClient
from sheets.parser import DataRow, parse_data_rows, parse_partners
from templates.messages import PropertyType, render

log = logging.getLogger(__name__)


def _zero_counts() -> dict:
    return {"total": 0, "sent": 0, "would_send": 0, "skipped_done": 0, "skipped_window": 0,
            "err_no_chat": 0, "err_no_type": 0, "err_tg": 0, "err_other": 0}


@dataclass
class RunSummary:
    run_id: str
    mode: str
    total: int
    sent: int
    skipped: int
    errors: int
    per_source: dict[str, dict] = field(default_factory=dict)
    no_type_rows: list[tuple[str, int, str]] = field(default_factory=list)

    def format(self) -> str:
        tag = "ТЕСТ (без отправки)" if self.mode == "dry" else "БОЕВОЙ"
        source_totals = " + ".join(f"{name}: {c['total']}" for name, c in self.per_source.items())
        lines = [
            f"Режим: {tag}",
            "",
            f"Всего строк: {self.total} ({source_totals})",
            "",
        ]
        if self.mode == "dry":
            would = sum(c.get("would_send", 0) for c in self.per_source.values())
            lines.append(f"Были бы отправлены сообщений: {would}")
        else:
            lines.append(f"Отправлено сообщений: {self.sent}")
        lines.append("")

        for name, c in self.per_source.items():
            lines.append(f"━━━ {name} ━━━")
            lines.append(f"  • уже закрыто: {c.get('skipped_done', 0)}")
            lines.append(f"  • в окне 7 дней: {c.get('skipped_window', 0)}")
            lines.append(f"  • нет партнёра в справочнике: {c.get('err_no_chat', 0)}")
            lines.append(f"  • не распознан тип: {c.get('err_no_type', 0)}")
            lines.append(f"  • Telegram отклонил: {c.get('err_tg', 0)}")
            if c.get('err_other', 0):
                lines.append(f"  • прочие сбои: {c.get('err_other', 0)}")
            lines.append("")

        if self.no_type_rows:
            lines.append("Не распознан тип имущества — проверь эти строки:")
            for src, idx, asset in self.no_type_rows[:20]:
                short = asset.replace("\n", " / ")
                if len(short) > 70:
                    short = short[:70] + "…"
                lines.append(f"  • ({src}) строка {idx}: {short}")
            if len(self.no_type_rows) > 20:
                lines.append(f"  … и ещё {len(self.no_type_rows) - 20}")

        return "\n".join(lines).rstrip()


def _is_tg_transient(exc: BaseException) -> bool:
    if isinstance(exc, (TelegramNetworkError, TelegramRetryAfter)):
        return True
    if isinstance(exc, (TelegramForbiddenError, TelegramBadRequest)):
        return False
    if isinstance(exc, TelegramAPIError):
        return True
    return False


def _is_sheets_transient(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", 0)
        return status >= 500
    return isinstance(exc, (ConnectionError, asyncio.TimeoutError))


class Runner:
    def __init__(self, settings: Settings, state: State, bot: Bot):
        self.s = settings
        self.state = state
        self.bot = bot
        self.sheets = SheetsClient(settings.google_creds_path, settings.sheet_id)

    async def run(self, mode: str, triggered_by: str,
                  source_filter: set[str] | None = None) -> RunSummary:
        assert mode in ("live", "dry")
        with acquire_runner_lock(self.s.mutex_file_path):
            return await self._run_locked(mode, triggered_by, source_filter)

    async def _run_locked(self, mode: str, triggered_by: str,
                          source_filter: set[str] | None) -> RunSummary:
        run_id = uuid.uuid4().hex[:8]
        self.state.create_run(run_id, mode, triggered_by)
        log.info("run start run_id=%s mode=%s triggered_by=%s filter=%s",
                 run_id, mode, triggered_by, source_filter)

        partner_map = await self._fetch_partners()

        per_source: dict[str, dict] = {}
        no_type_rows: list[tuple[str, int, str]] = []

        sources = [s for s in self.s.data_sources
                   if source_filter is None or s.tab_name in source_filter]

        for source in sources:
            counts = _zero_counts()
            try:
                data = await self._fetch_tab(source.tab_name)
            except Exception:
                log.exception("failed to fetch tab %r", source.tab_name)
                per_source[source.tab_name] = counts
                continue
            rows = parse_data_rows(data, source, self.s)
            counts["total"] = len(rows)
            for row in rows:
                sent_any = await self._process_row(run_id, source, row, partner_map, mode,
                                                    counts, no_type_rows)
                if sent_any:
                    await asyncio.sleep(self.s.message_delay_seconds)
            per_source[source.tab_name] = counts

        total = sum(c["total"] for c in per_source.values())
        sent = sum(c["sent"] for c in per_source.values())
        skipped = sum(c["skipped_done"] + c["skipped_window"] for c in per_source.values())
        errors = sum(c["err_no_chat"] + c["err_no_type"] + c["err_tg"] + c["err_other"]
                     for c in per_source.values())

        summary = RunSummary(run_id, mode, total, sent, skipped, errors, per_source, no_type_rows)
        self.state.finish_run(run_id, total, sent, skipped, errors, per_source)
        log.info("run done run_id=%s per_source=%s", run_id, per_source)
        return summary

    async def _fetch_partners(self) -> dict[str, tuple[int, int | None]]:
        loop = asyncio.get_event_loop()
        partners = await retry_async(
            lambda: loop.run_in_executor(None, self.sheets.fetch_tab,
                                         self.s.sheet_tab_partners, True),
            self.s.retry_delays, _is_sheets_transient, context="sheets:partners",
        )
        return parse_partners(partners, self.s)

    async def _fetch_tab(self, tab_name: str) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await retry_async(
            lambda: loop.run_in_executor(None, self.sheets.fetch_tab, tab_name),
            self.s.retry_delays, _is_sheets_transient, context=f"sheets:{tab_name}",
        )

    async def _process_row(self, run_id: str, source: DataSource, row: DataRow,
                           partner_map: dict[str, tuple[int, int | None]], mode: str, counts: dict,
                           no_type_rows: list[tuple[str, int, str]]) -> bool:
        if row.done:
            counts["skipped_done"] += 1
            self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                row.asset, None, "SKIPPED_DONE", None, 0)
            return False

        chat_ref = partner_map.get(row.partner.strip().lower()) if row.partner else None
        if chat_ref is None:
            counts["err_no_chat"] += 1
            self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                row.asset, None, "ERROR", "ERROR_NO_CHAT", 0)
            return False
        chat_id, thread_id = chat_ref

        if not row.assets_by_type:
            counts["err_no_type"] += 1
            no_type_rows.append((source.tab_name, row.row_index, row.asset))
            self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                row.asset, None, "ERROR", "ERROR_NO_TYPE", 0)
            return False

        # Collect blocks to send: skip types in window, render the rest
        to_send: list[tuple[PropertyType, str, str, str]] = []  # (ptype, asset_text, new_key, block)
        for ptype, assets in row.assets_by_type.items():
            new_key = f"{source.tab_name}:r{row.row_index}:{ptype.value}"
            legacy_key = f"r{row.row_index}:{ptype.value}"
            asset_text = ", ".join(assets)
            if self.state.is_within_window(row.partner, new_key,
                                            self.s.idempotency_window_hours,
                                            legacy_keys=[legacy_key]):
                counts["skipped_window"] += 1
                self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                    asset_text, ptype.value, "SKIPPED_WINDOW", None, 0)
                continue
            block = render(ptype, fio=row.fio or row.partner, asset=asset_text)
            to_send.append((ptype, asset_text, new_key, block))

        if not to_send:
            return False

        if mode == "dry":
            for ptype, asset_text, _key, _block in to_send:
                counts["would_send"] += 1
                self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                    asset_text, ptype.value, "DRY_OK", None, 0)
            return False

        final_text = "\n\n".join(block for _, _, _, block in to_send)

        try:
            for chunk in _split_by_limit(final_text, 4000):
                await self._send_with_retry(chat_id, chunk, thread_id)
            for ptype, asset_text, new_key, _block in to_send:
                counts["sent"] += 1
                self.state.mark_success(row.partner, new_key)
                self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                    asset_text, ptype.value, "SENT", None, 1)
            await self._log_to_sheet(source, row.row_index)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                for chunk in _split_by_limit(final_text, 4000):
                    await self._send_with_retry(chat_id, chunk, thread_id)
                for ptype, asset_text, new_key, _block in to_send:
                    counts["sent"] += 1
                    self.state.mark_success(row.partner, new_key)
                    self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                        asset_text, ptype.value, "SENT", None, 1)
                await self._log_to_sheet(source, row.row_index)
                return True
            except BaseException as exc:
                for ptype, asset_text, _key, _block in to_send:
                    counts["err_tg"] += 1
                    self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                        asset_text, ptype.value, "ERROR",
                                        f"ERROR_TELEGRAM:{type(exc).__name__}", 0)
                return False
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            for ptype, asset_text, _key, _block in to_send:
                counts["err_tg"] += 1
                self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                    asset_text, ptype.value, "ERROR",
                                    f"ERROR_TELEGRAM:{type(exc).__name__}", 0)
            return False
        except BaseException as exc:
            log.exception("send failed source=%s row=%d", source.tab_name, row.row_index)
            for ptype, asset_text, _key, _block in to_send:
                counts["err_other"] += 1
                self.state.log_send(run_id, source.tab_name, row.row_index, row.partner,
                                    asset_text, ptype.value, "ERROR",
                                    f"ERROR_OTHER:{type(exc).__name__}", 0)
            return False

    async def _log_to_sheet(self, source: DataSource, row_index: int) -> None:
        tz = ZoneInfo(self.s.timezone)
        note = datetime.now(tz).strftime("%d.%m.%Y")
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self.sheets.append_log_cell,
                source.tab_name,
                source.col_write_log,
                row_index,
                note,
            )
        except Exception:
            log.exception("failed to write log-cell source=%s row=%d",
                          source.tab_name, row_index)

    async def _send_with_retry(self, chat_id: int, text: str, thread_id: int | None = None) -> None:
        async def _call():
            kwargs = {}
            if thread_id is not None:
                kwargs["message_thread_id"] = thread_id
            await self.bot.send_message(chat_id, text, **kwargs)
        ctx = f"tg:send:{chat_id}" + (f"/{thread_id}" if thread_id is not None else "")
        await retry_async(_call, self.s.retry_delays, _is_tg_transient, context=ctx)


def _split_by_limit(text: str, limit: int) -> list[str]:
    """Split a long message so each chunk ≤ limit chars. Prefers \\n\\n boundaries."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = remaining.rfind("\n", 0, limit)
        if cut == -1 or cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
