from enum import Enum


class PropertyType(str, Enum):
    REALTY = "realty"
    VEHICLE = "vehicle"
    WEAPON = "weapon"


TEMPLATE_REALTY = (
    "{fio} - по {asset} "
    "необходимы фото и контакты лица, "
    "которое будет осуществлять показ в период торгов."
)

TEMPLATE_VEHICLE = (
    "{fio} - по {asset} "
    "необходимы подписанный договор ответственного хранения, ПТС, СТС, "
    "актуальные фотографии внешнего состояния, салон, подкапотное пространство, "
    "пробег на одометре; пояснения по техническому состоянию на данный момент; "
    "адрес местонахождения авто; "
    "контакты лица, которое будет осуществлять показ в период торгов."
)

TEMPLATE_WEAPON = (
    "{fio} - по {asset} "
    "необходимы правоустанавливающие документы, фотографии, "
    "адрес хранения и контакт хранителя"
)


TEMPLATES: dict[PropertyType, str] = {
    PropertyType.REALTY: TEMPLATE_REALTY,
    PropertyType.VEHICLE: TEMPLATE_VEHICLE,
    PropertyType.WEAPON: TEMPLATE_WEAPON,
}


def render(ptype: PropertyType, fio: str, asset: str) -> str:
    return TEMPLATES[ptype].format(fio=fio, asset=asset)
