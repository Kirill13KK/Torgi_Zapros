from enum import Enum


class PropertyType(str, Enum):
    REALTY = "realty"
    VEHICLE = "vehicle"
    WEAPON = "weapon"


_BODY = (
    "Должник: {fio}\n"
    "Вид имущества: {asset}\n"
    "Необходимо: {need}"
)

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

TEMPLATE_REALTY = _BODY.replace("{need}", NEED_REALTY)
TEMPLATE_VEHICLE = _BODY.replace("{need}", NEED_VEHICLE)
TEMPLATE_WEAPON = _BODY.replace("{need}", NEED_WEAPON)


TEMPLATES: dict[PropertyType, str] = {
    PropertyType.REALTY: TEMPLATE_REALTY,
    PropertyType.VEHICLE: TEMPLATE_VEHICLE,
    PropertyType.WEAPON: TEMPLATE_WEAPON,
}


def render(ptype: PropertyType, fio: str, asset: str) -> str:
    return TEMPLATES[ptype].format(fio=fio, asset=asset)
