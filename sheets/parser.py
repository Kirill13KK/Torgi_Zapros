import re
from dataclasses import dataclass, field

from config.settings import DataSource, Settings
from sheets.client import is_default_white
from templates.messages import PropertyType


_CASE_RE = re.compile(r"^[АAа]\s*\d+-\d+/\d{4}$")


def _is_case_number(s: str) -> bool:
    return bool(_CASE_RE.match((s or "").strip()))


PREFIXES: list[tuple[str, PropertyType]] = [
    # weapon — длинные формы раньше коротких
    ("Оружение", PropertyType.WEAPON),
    ("Оружие", PropertyType.WEAPON),
    ("Оруж", PropertyType.WEAPON),
]

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

_PREFIX_SEPARATORS = " :-\t.,—–"


@dataclass
class DataRow:
    source_name: str
    row_index: int
    partner: str
    fio: str
    asset: str
    done: bool
    assets_by_type: dict[PropertyType, list[str]] = field(default_factory=dict)


def parse_data_rows(raw_rows: list[dict], source: DataSource, s: Settings) -> list[DataRow]:
    out: list[DataRow] = []
    for row in raw_rows:
        if row["row_index"] < source.first_row:
            continue
        cells = row["cells"]
        partner = _val(cells, source.col_partner)
        if source.col_partner_fallback:
            fallback = _val(cells, source.col_partner_fallback)
            if _is_case_number(partner) and fallback and not _is_case_number(fallback):
                partner = fallback
            elif not partner and fallback:
                partner = fallback
        fio = _val(cells, source.col_fio)
        asset = _val(cells, source.col_asset)
        done_cell = cells.get(source.col_done_flag, {})
        done = not is_default_white(done_cell.get("bg"))

        if not partner and not asset:
            continue

        out.append(DataRow(
            source_name=source.tab_name,
            row_index=row["row_index"],
            partner=partner,
            fio=fio,
            asset=asset,
            done=done,
            assets_by_type=classify_assets(asset, s),
        ))
    return out


def parse_partners(raw_rows: list[dict], s: Settings) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for row in raw_rows:
        if row["row_index"] < s.partners_first_row:
            continue
        cells = row["cells"]
        name = _val(cells, s.partners_col_name)
        chat_id_raw = _val(cells, s.partners_col_chat_id)
        if not name or not chat_id_raw:
            continue
        try:
            mapping[name.strip().lower()] = int(chat_id_raw.strip())
        except ValueError:
            continue
    return mapping


def classify_assets(text: str, s: Settings) -> dict[PropertyType, list[str]]:
    """
    Split the cell into chunks (by newline) and classify each chunk.
    Priority order for each chunk:
      1. Explicit prefix (ТС / НД / Оруж...) — prefix is stripped from the returned text.
      2. Keyword substring match (fallback).
    Returns dict {type: [asset-chunk-text, ...]}. Empty dict if nothing classified.
    """
    result: dict[PropertyType, list[str]] = {}
    if not text:
        return result
    chunks = [c.strip() for c in text.split("\n") if c.strip()]
    for chunk in chunks:
        ptype, clean = _extract_prefix(chunk)
        if ptype is None:
            ptype = _keyword_classify(chunk, s)
            clean = chunk
        if ptype is None:
            continue
        result.setdefault(ptype, []).append(clean)
    return result


def _extract_prefix(chunk: str) -> tuple[PropertyType | None, str]:
    low = chunk.lower()
    for prefix, ptype in PREFIXES:
        p = prefix.lower()
        if not low.startswith(p):
            continue
        if len(chunk) == len(prefix):
            continue
        if chunk[len(prefix)] not in _PREFIX_SEPARATORS:
            continue
        rest = chunk[len(prefix):].lstrip(_PREFIX_SEPARATORS)
        if rest:
            return ptype, rest
    return None, chunk


def _val(cells: dict, letter: str) -> str:
    c = cells.get(letter)
    if not c:
        return ""
    v = c.get("value")
    return v.strip() if isinstance(v, str) else ""


def _keyword_classify(text: str, s: Settings) -> PropertyType | None:
    if not text:
        return None
    a = text.lower()
    for kw in s.weapon_keywords:
        if kw in a:
            return PropertyType.WEAPON
    for kw in s.vehicle_keywords:
        if kw in a:
            return PropertyType.VEHICLE
    if _CYRILLIC_RE.search(text):
        return PropertyType.REALTY
    return None
