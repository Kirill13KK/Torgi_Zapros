from enum import Enum


class PropertyType(str, Enum):
    REALTY = "realty"
    VEHICLE = "vehicle"
    WEAPON = "weapon"
    BUSINESS = "business"


EMOJI_CAR = "🚗"
EMOJI_TRACTOR = "🚜"
EMOJI_MOTO = "🛵"
EMOJI_BOAT = "🛶"
EMOJI_WEAPON = "🔫"
EMOJI_HOUSE = "🏡"
EMOJI_PLOT = "🏕"
EMOJI_BUSINESS = "📄"


NEED_REALTY = (
    "фото и контакты лица, которое будет осуществлять показ в период торгов."
)

NEED_VEHICLE = (
    "подписанный договор ответственного хранения, ПТС, СТС, "
    "актуальные фотографии внешнего состояния, салон, подкапотное пространство, "
    "пробег на одометре; пояснения по техническому состоянию на данный момент; "
    "адрес местонахождения авто; "
    "контакты лица, которое будет осуществлять показ в период торгов."
)

NEED_WEAPON = (
    "правоустанавливающие документы, фотографии, "
    "адрес хранения и контакт хранителя."
)

NEED_BUSINESS = (
    "правоустанавливающие документы, устав, "
    "сведения о доходах (при наличии) за последние 3 года."
)

NEEDS: dict[PropertyType, str] = {
    PropertyType.REALTY: NEED_REALTY,
    PropertyType.VEHICLE: NEED_VEHICLE,
    PropertyType.WEAPON: NEED_WEAPON,
    PropertyType.BUSINESS: NEED_BUSINESS,
}


_TEMPLATE = (
    "👤 Должник: {fio}\n"
    "\n"
    "{emoji} Вид имущества: {asset}\n"
    "\n"
    "⁉️ Необходимо: {need}"
)


def pick_emoji(ptype: PropertyType, asset: str) -> str:
    a = (asset or "").lower()
    if ptype == PropertyType.BUSINESS:
        return EMOJI_BUSINESS
    if ptype == PropertyType.WEAPON:
        return EMOJI_WEAPON
    if ptype == PropertyType.VEHICLE:
        if "трактор" in a:
            return EMOJI_TRACTOR
        if any(k in a for k in ("мотоцикл", "квадроцикл", "снегоход", "снегоболотоход", "скутер")):
            return EMOJI_MOTO
        if any(k in a for k in ("лодк", "яхт", "катер", "моторн", "мотор")):
            return EMOJI_BOAT
        return EMOJI_CAR
    plot_markers = ("участок", "зем")
    building_markers = ("дом", "квартир", "коттедж", "здание", "помещен", "комнат", "гараж", "апартамент", "строение")
    has_plot = any(k in a for k in plot_markers)
    has_building = any(k in a for k in building_markers)
    if has_plot and not has_building:
        return EMOJI_PLOT
    return EMOJI_HOUSE


_DEBTOR_OWNERSHIP = "Собственность должника"


def render(ptype: PropertyType, fio: str, asset: str, bank: str = "") -> str:
    if not bank:
        ownership = ""
    elif bank == _DEBTOR_OWNERSHIP:
        ownership = f"\n\n📇 Вид собственности: {_DEBTOR_OWNERSHIP}"
    else:
        ownership = f"\n\n📇 Вид собственности: В залоге у {bank}"
    return (
        f"👤 Должник: {fio}\n"
        f"\n"
        f"{pick_emoji(ptype, asset)} Вид имущества: {asset}"
        f"{ownership}\n"
        f"\n"
        f"⁉️ Необходимо: {NEEDS[ptype]}"
    )
