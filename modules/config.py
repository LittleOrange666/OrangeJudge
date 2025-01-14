from copy import deepcopy
from dataclasses import fields, dataclass, field
from pathlib import Path
from typing import TypeVar, Type

import yaml
from loguru import logger

from .objs import as_dict, DataMeta

T = TypeVar('T')


class ConfigError(Exception):
    pass


config_file = Path("data/config.yaml").absolute()

if config_file.is_file():
    with config_file.open() as f:
        config_data = yaml.load(f, yaml.loader.SafeLoader)
else:
    config_data = {}

logger.info("config=" + str(config_data))


def save_config():
    with config_file.open("w") as file:
        yaml.dump(as_dict(config), file)


def ConfigProperty(name: str, _type: Type[T], _default_val: T):
    def factory():
        return _type(deepcopy(_default_val))

    return field(default_factory=factory, metadata={"name": name, "type": _type})


def ConfigCategory(name: str, _type: Type[T]):
    def factory():
        return _type()
    return field(default_factory=factory, metadata={"name": name, "type": _type})


@dataclass
class SmtpConfig(metaclass=DataMeta):
    """
    Configuration class for SMTP settings.

    Attributes:
        host (str): The SMTP server address.
        port (int): The port number for the SMTP server.
        user (str): The username for the SMTP server.
        password (str): The password for the SMTP server.
        enabled (bool): Whether the SMTP is enabled.
        limit (str): The rate limit for verification codes.
    """
    host: str = ConfigProperty("SMTP伺服器", str, "smtp.gmail.com")
    port: int = ConfigProperty("SMTP伺服器連接埠", int, 587)
    user: str = ConfigProperty("SMTP使用者名稱(email)", str, "user@gmail.com")
    password: str = ConfigProperty("SMTP使用者密碼", str, "password")
    enabled: bool = ConfigProperty("SMTP是否啟用", bool, False)
    limit: str = ConfigProperty("驗證碼頻率限制", str, "1 per 20 second")


@dataclass
class ServerConfig(metaclass=DataMeta):
    """
    Configuration class for server settings.

    Attributes:
        port (int): The port number for the server.
        workers (int): The number of WSGI workers.
        timeout (int): The WSGI timeout duration.
        limits (list[str]): The list of request rate limits.
        file_limit (str): The rate limit for file downloads.
    """
    port: int = ConfigProperty("此伺服器的連接埠", int, 8080)
    workers: int = ConfigProperty("WSGI並行數量", int, 4)
    timeout: int = ConfigProperty("WSGI超時時間", int, 120)
    limits: list[str] = ConfigProperty("請求頻率限制列表", list, ("30 per 30 second", "3 per 1 second"))
    file_limit: str = ConfigProperty("檔案下載頻率限制", str, "30 per 5 second")
    admin_fast: bool = ConfigProperty("管理員可無視請求頻率限制", bool, False)


@dataclass
class JudgeConfig(metaclass=DataMeta):
    """
    Configuration class for judge system settings.

    Attributes:
        workers (int): The number of concurrent workers.
        period (int): The scan period for the judge system.
        limit (str): The submission rate limit.
        pending_limit (int): The limit for pending submissions.
        file_size (int): The file size limit in KB.
        save_period (int): The save period for the judge system.
    """
    workers: int = ConfigProperty("評測系統並行數量", int, 1)
    period: int = ConfigProperty("評測系統掃描週期(s)", int, 3)
    limit: str = ConfigProperty("提交頻率限制", str, "1 per 10 second")
    pending_limit: int = ConfigProperty("等待中提交數量限制", int, 1)
    file_size: int = ConfigProperty("檔案大小限制(KB)", int, 100)
    save_period: int = ConfigProperty("評測系統儲存週期(每完成幾筆測資更新狀態)", int, 3)


@dataclass
class DebugConfig(metaclass=DataMeta):
    """
    Configuration class for debug settings.

    Attributes:
        disable_csrf (bool): Whether to disable CSRF protection.
        single_secret (bool): Whether to use a fixed SECRET_KEY.
    """
    disable_csrf: bool = ConfigProperty("關閉CSRF保護", bool, False)
    single_secret: bool = ConfigProperty("使用固定的SECRET_KEY", bool, False)


@dataclass
class AccountConfig(metaclass=DataMeta):
    """
    Configuration class for account settings.

    Attributes:
        signup (bool): Whether to allow user registration.
    """
    signup: bool = ConfigProperty("是否開放註冊", bool, True)


@dataclass
class Config(metaclass=DataMeta):
    """
    Configuration class that aggregates all configuration categories.

    Attributes:
        smtp (SmtpConfig): The SMTP configuration settings.
        server (ServerConfig): The server configuration settings.
        judge (JudgeConfig): The judge system configuration settings.
        debug (DebugConfig): The debug configuration settings.
        account (AccountConfig): The account system configuration settings.
    """
    smtp: SmtpConfig = ConfigCategory("SMTP設定", SmtpConfig)
    server: ServerConfig = ConfigCategory("伺服器設定", ServerConfig)
    judge: JudgeConfig = ConfigCategory("評測系統設定", JudgeConfig)
    debug: DebugConfig = ConfigCategory("除錯設定", DebugConfig)
    account: AccountConfig = ConfigCategory("帳號系統設定", AccountConfig)


config = Config(**config_data)
smtp = config.smtp
server = config.server
judge = config.judge
debug = config.debug
account = config.account
save_config()


def init():
    pass


def get_fields():
    categories = fields(config)
    ret = []
    for category in categories:
        for slot in fields(category.type):
            ret.append((category.name + "." + slot.name,category.metadata["name"], slot.metadata["name"], slot.type))
    return ret