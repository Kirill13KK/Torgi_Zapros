from dataclasses import dataclass
from functools import cached_property, lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class DataSource:
    tab_name: str
    col_partner: str
    col_fio: str
    col_asset: str
    col_done_flag: str
    col_write_log: str
    col_partner_fallback: str = ""
    first_row: int = 2


DEFAULT_DATA_SOURCES: list[DataSource] = [
    DataSource(
        tab_name="Непризнанные",
        col_partner="D",
        col_fio="B",
        col_asset="E",
        col_done_flag="H",
        col_write_log="I",
    ),
    DataSource(
        tab_name="Залоги",
        col_partner="D",
        col_fio="B",
        col_asset="E",
        col_done_flag="G",
        col_write_log="I",
    ),
    DataSource(
        tab_name="Собрания",
        col_partner="D",
        col_partner_fallback="C",
        col_fio="B",
        col_asset="E",
        col_done_flag="I",
        col_write_log="J",
    ),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tg_bot_token: str

    google_creds_path: str = "./credentials/google.json"
    sheet_id: str
    sheet_tab_partners: str = "Партнёры"

    realty_keywords_csv: str = (
        "зем,участок,квартир,дом,гараж,нежил,здание,помещен,комнат,"
        "зу ,зу1,зу.,кв ,кв.,кв1,ком ,ком1,д1/,д 1/,ком.,апартамент,"
        "объект незавершен,объект незаверш,строительств,офис,склад,коттедж,"
        "дача,строение"
    )
    vehicle_keywords_csv: str = (
        "hyundai,kia,ford,toyota,bmw,nissan,lada,ваз,audi,mercedes,volkswagen,"
        "vw,skoda,renault,mitsubishi,mazda,honda,subaru,volvo,chevrolet,opel,"
        "peugeot,citroen,fiat,porsche,infiniti,lexus,jaguar,land rover,"
        "range rover,cruiser,лада,хонда,тойота,ниссан,киа,форд,бмв,мерседес,"
        "автомобил,brilliance,geely,chery,газ,заз,niva,нива,changan,changa,"
        "kaiyi,great wall,great wal,ssang,опель,шевроле,лексус,мазда,тоу,гв,"
        "грузов,мото,scooter,скутер,прицеп,шкода,катер,лодк,моторн,яхт,"
        "рапид,октавия,йети,кодиак,2017г,2018г,2019г,2020г,2021г,"
        "2022г,2023г,2024г,2025г,ferrari,ferari,феррари,lamborghini,ламборгини,"
        "bentley,бентли,rolls royce,raptor,уаз,камаз,маз,краз,fiat,фиат,dodge,"
        "ram,джип,jeep,tesla,byd,byd qcj"
    )
    weapon_keywords_csv: str = (
        "оруж,ружь,пистолет,карабин,винтовк,ствол,тоз,сайг,иж-,мосин,сайга,"
        "мр-,бекас"
    )

    partners_header_row: int = 1
    partners_first_row: int = 2
    partners_col_name: str = "A"
    partners_col_chat_id: str = "B"

    service_chat_id: int | None = None
    admin_user_ids_csv: str = ""

    interval_days: int = 7
    idempotency_window_hours: int = 168
    retry_max: int = 2
    retry_delays_csv: str = "5,30"
    timezone: str = "Europe/Moscow"
    message_delay_seconds: float = 3.0

    cron_day_of_week: str = "mon"
    cron_hour: int = 10
    cron_minute: int = 0

    log_level: str = "INFO"
    state_db_path: str = "./data/state.db"
    mutex_file_path: str = "./data/runner.lock"

    @property
    def data_sources(self) -> list[DataSource]:
        return DEFAULT_DATA_SOURCES

    @cached_property
    def admin_user_ids(self) -> list[int]:
        return _parse_int_csv(self.admin_user_ids_csv)

    @cached_property
    def retry_delays(self) -> list[int]:
        return _parse_int_csv(self.retry_delays_csv)

    @cached_property
    def realty_keywords(self) -> list[str]:
        return _parse_str_csv(self.realty_keywords_csv)

    @cached_property
    def vehicle_keywords(self) -> list[str]:
        return _parse_str_csv(self.vehicle_keywords_csv)

    @cached_property
    def weapon_keywords(self) -> list[str]:
        return _parse_str_csv(self.weapon_keywords_csv)


def _parse_int_csv(s: str) -> list[int]:
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def _parse_str_csv(s: str) -> list[str]:
    return [x.strip().lower() for x in s.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
