"""
Tests for 'Вид собственности' line in render() and _normalize_bank().
Google/Telegram deps are mocked out — no real API calls.
"""
import sys
import types
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Stub out Google and aiogram before any project import touches them
# ---------------------------------------------------------------------------
for mod in (
    "google", "google.oauth2", "google.oauth2.service_account",
    "googleapiclient", "googleapiclient.discovery", "googleapiclient.errors",
    "aiogram", "aiogram.types", "aiogram.exceptions",
):
    sys.modules.setdefault(mod, types.ModuleType(mod))

# Provide the one symbol sheets.client needs
google_stub = sys.modules["google.oauth2.service_account"]
google_stub.Credentials = object  # type: ignore[attr-defined]

# Provide is_default_white so sheets.client can be imported
client_stub = types.ModuleType("sheets.client")
client_stub.is_default_white = lambda bg: bg is None or all(c >= 0.98 for c in bg)  # type: ignore[attr-defined]
sys.modules["sheets.client"] = client_stub

# Now safe to import project modules
import pytest  # noqa: E402
from templates.messages import PropertyType, render  # noqa: E402
from sheets.parser import _normalize_bank  # noqa: E402

# ---------------------------------------------------------------------------
_PTYPE = PropertyType.VEHICLE
_FIO = "Иванов"
_ASSET = "Toyota"
OWNERSHIP_LINE = "📇 Вид собственности:"


# ---------------------------------------------------------------------------
# _normalize_bank — таблица сценариев
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("",                       ""),
    ("-",                      "Собственность должника"),
    ("–",                      "Собственность должника"),
    ("—",                      "Собственность должника"),
    ("−",                      "Собственность должника"),
    ("  —  ",                  "Собственность должника"),
    ("Сбербанк",               "Сбербанк"),
    ("АО Тбанк",               "АО Тбанк"),
    ("Собственность должника", "Собственность должника"),
])
def test_normalize_bank(raw, expected):
    assert _normalize_bank(raw) == expected


# ---------------------------------------------------------------------------
# render() — четыре основных сценария по ТЗ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bank,contains,not_contains", [
    # 1. Пустая ячейка — строки «Вид собственности» нет
    ("", None, OWNERSHIP_LINE),
    # 2. Прочерк (уже нормализован парсером) — без «В залоге у»
    ("Собственность должника",
     "📇 Вид собственности: Собственность должника",
     "В залоге у Собственность"),
    # 3. Явное значение «Собственность должника» — то же поведение
    ("Собственность должника",
     "📇 Вид собственности: Собственность должника",
     "В залоге у Собственность"),
    # 4. Название банка — «В залоге у {банк}»
    ("АО Тбанк",
     "📇 Вид собственности: В залоге у АО Тбанк",
     None),
])
def test_render_ownership(bank, contains, not_contains):
    text = render(_PTYPE, _FIO, _ASSET, bank=bank)
    if contains:
        assert contains in text, f"Не найдено {contains!r} в:\n{text}"
    if not_contains:
        assert not_contains not in text, f"Найдено лишнее {not_contains!r} в:\n{text}"


# ---------------------------------------------------------------------------
# Точные примеры из ТЗ
# ---------------------------------------------------------------------------

def test_exact_dash_message():
    """Прочерк → 'Собственность должника', без 'В залоге у'."""
    bank = _normalize_bank("—")
    text = render(_PTYPE, _FIO, _ASSET, bank=bank)
    assert "📇 Вид собственности: Собственность должника" in text
    assert "В залоге у Собственность" not in text


def test_exact_bank_message():
    """Название банка → 'В залоге у Сбербанк'."""
    text = render(_PTYPE, _FIO, _ASSET, bank="Сбербанк")
    assert "📇 Вид собственности: В залоге у Сбербанк" in text


def test_empty_bank_no_section():
    """Пустой bank — строки Вид собственности нет."""
    text = render(_PTYPE, _FIO, _ASSET, bank="")
    assert OWNERSHIP_LINE not in text
