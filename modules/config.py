from copy import deepcopy
from dataclasses import fields, dataclass, field
from pathlib import Path
from typing import TypeVar, Type

import yaml
from loguru import logger

from .objs import as_dict

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


class ConfigCategory:
    """
    Base class for configuration categories. It initializes the configuration
    category with the provided data, key, and name. It also validates the data
    and sets the attributes based on the fields defined in the subclass.

    Attributes:
        key (str): The key for the configuration category.
        name (str): The name of the configuration category.
        source (dict): The source data for the configuration.
    """

    def __init__(self, data: dict, key: str, name: str):
        """
        Initializes the ConfigCategory with the provided data, key, and name.

        Args:
            data (dict): The configuration data.
            key (str): The key for the configuration category.
            name (str): The name of the configuration category.

        Raises:
            ConfigError: If the key is not a dictionary in the data.
        """
        self.key = key
        self.name = name
        if key not in data:
            data[key] = {}
        if not isinstance(data[key], dict):
            raise ConfigError(f"'{key}' is not a dict")
        my_data = data[key]
        self.source = data
        for field in fields(self):
            val = my_data.get(field.name, field.default)
            tp = field.type
            if hasattr(tp, "__origin__"):
                tp = tp.__origin__
            if isinstance(val, tp):
                setattr(self, field.name, val)
            else:
                raise ConfigError(f"'{key}.{field.name}' is not a {field.type.__name__}")


def ConfigProperty(name: str, _type: Type[T], _default_val: T):
    def factory():
        return deepcopy(_default_val)

    return field(default_factory=factory, metadata={"name": name, "type": _type})


@dataclass
class SmtpConfig(ConfigCategory):
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

    def __init__(self, data: dict):
        """
        Initializes the SmtpConfig with the provided data.

        Args:
            data (dict): The configuration data.
        """
        super().__init__(data, "smtp", "SMTP設定")


@dataclass
class ServerConfig(ConfigCategory):
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
    limits: list[str] = ConfigProperty("請求頻率限制列表", list, ["30 per 30 second", "3 per 1 second"])
    file_limit: str = ConfigProperty("檔案下載頻率限制", str, "30 per 5 second")

    def __init__(self, data: dict):
        """
        Initializes the ServerConfig with the provided data.

        Args:
            data (dict): The configuration data.
        """
        super().__init__(data, "server", "伺服器設定")


@dataclass
class JudgeConfig(ConfigCategory):
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

    def __init__(self, data: dict):
        """
        Initializes the JudgeConfig with the provided data.

        Args:
            data (dict): The configuration data.
        """
        super().__init__(data, "judge", "評測系統設定")


@dataclass
class DebugConfig(ConfigCategory):
    """
    Configuration class for debug settings.

    Attributes:
        disable_csrf (bool): Whether to disable CSRF protection.
        single_secret (bool): Whether to use a fixed SECRET_KEY.
    """
    disable_csrf: bool = ConfigProperty("關閉CSRF保護", bool, False)
    single_secret: bool = ConfigProperty("使用固定的SECRET_KEY", bool, False)

    def __init__(self, data: dict):
        """
        Initializes the DebugConfig with the provided data.

        Args:
            data (dict): The configuration data.
        """
        super().__init__(data, "debug", "除錯設定")


@dataclass
class AccountConfig(ConfigCategory):
    """
    Configuration class for account settings.

    Attributes:
        signup (bool): Whether to allow user registration.
    """
    signup: bool = ConfigProperty("是否開放註冊", bool, True)

    def __init__(self, data: dict):
        """
        Initializes the AccountConfig with the provided data.

        Args:
            data (dict): The configuration data.
        """
        super().__init__(data, "account", "帳號系統設定")


@dataclass
class Config:
    smtp: SmtpConfig
    server: ServerConfig
    judge: JudgeConfig
    debug: DebugConfig
    account: AccountConfig

    def __init__(self, data: dict):
        self.smtp = SmtpConfig(data)
        self.server = ServerConfig(data)
        self.judge = JudgeConfig(data)
        self.debug = DebugConfig(data)
        self.account = AccountConfig(data)


config = Config(config_data)
smtp = config.smtp
server = config.server
judge = config.judge
debug = config.debug
account = config.account
save_config()


def init():
    pass
