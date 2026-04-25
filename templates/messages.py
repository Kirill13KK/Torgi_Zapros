from enum import Enum


class PropertyType(str, Enum):
    REALTY = "realty"
    VEHICLE = "vehicle"
    WEAPON = "weapon"


EMOJI_CAR = "🚗"
EMOJI_TRACTOR = "🚜"
EMOJI_MOTO = "🛵"
EMOJI_BOAT = "🛶"
EMOJI_WEAPON = "🔫"
EMOJI_HOUSE = "🏡"
EMOJI_PLOT = "🏕"


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

NEEDS: dict[PropertyType, str] = {
    PropertyType.REALTY: NEED_REALTY,
    PropertyType.VEHICLE: NEED_VEHICLE,
    PropertyType.WEAPON: NEED_WEAPON,
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


def render(ptype: PropertyType, fio: str, asset: str) -> str:
    return _TEMPLATE.format(
        fio=fio,
        emoji=pick_emoji(ptype, asset),
        asset=asset,
        need=NEEDS[ptype],
    )
