import secrets
from typing import Generic, TypeVar, Type

import yaml

T = TypeVar('T')


class ConfigError(Exception):
    pass


with open("config.yaml", "r") as f:
    config = yaml.load(f, yaml.loader.SafeLoader)

print("config=", config)


def save_config():
    with open("config.yaml", "w") as file:
        yaml.dump(config, file)


class ConfigCategory:

    def __init__(self, data: dict, key: str, name: str):
        self.key = key
        self.name = name
        if key not in data:
            data[key] = {}
        if not isinstance(data[key], dict):
            raise ConfigError(f"'{key}' is not a dict")
        self.data = data[key]
        self.source = data


class ConfigProperty(Generic[T]):
    __slots__ = ("_value", "name", "_key", "_type", "_parent")

    def __init__(self, parent: ConfigCategory, key: str, name: str, _type: Type[T], _default: T):
        if key not in parent.data:
            parent.data[key] = _default
            save_config()
        if not isinstance(parent.data[key], _type):
            raise ConfigError(f"'{parent.key}.{key}' is not a {_type.__name__}")
        self._value: T = parent.data[key]
        self._parent = parent
        self.name = name
        self._key = key
        self._type = _type

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, new_val: T):
        self._value = new_val
        self._parent.data[self._key] = new_val
        save_config()


class SmtpConfig(ConfigCategory):
    def __init__(self, data: dict):
        super().__init__(data, "smtp", "SMTP設定")
        self.host = ConfigProperty[str](self, "host", "SMTP伺服器", str, "smtp.gmail.com")
        self.port = ConfigProperty[int](self, "port", "SMTP伺服器連接埠", int, 587)
        self.user = ConfigProperty[str](self, "user", "SMTP使用者名稱(email)", str, "user@gmail.com")
        self.password = ConfigProperty[str](self, "password", "SMTP使用者密碼", str, "password")
        self.enabled = ConfigProperty[bool](self, "enabled", "SMTP是否啟用", bool, False)


smtp = SmtpConfig(config)


class ServerConfig(ConfigCategory):
    def __init__(self, data: dict):
        super().__init__(data, "server", "伺服器設定")
        self.port = ConfigProperty[int](self, "port", "此伺服器的連接埠", int, 8080)
        self.workers = ConfigProperty[int](self, "workers", "WSGI並行數量", int, 4)
        self.timeout = ConfigProperty[int](self, "timeout", "WSGI超時時間", int, 120)
        self.limits = ConfigProperty[list[str]](self, "limits", "請求頻率限制列表", list,
                                                ["20 per 30 second", "2 per 1 second"])


server = ServerConfig(config)


class JudgeConfig(ConfigCategory):
    def __init__(self, data: dict):
        super().__init__(data, "judge", "評測系統設定")
        self.workers = ConfigProperty[int](self, "workers", "評測系統並行數量", int, 1)
        self.limit = ConfigProperty[str](self, "limit", "提交頻率限制", str, "1 per 10 second")
        self.file_size = ConfigProperty[int](self, "file_size", "檔案大小限制(KB)", int, 100)


judge = JudgeConfig(config)


class DebugConfig(ConfigCategory):
    def __init__(self, data: dict):
        super().__init__(data, "debug", "除錯設定")
        self.log = ConfigProperty[bool](self, "log", "除錯紀錄是否啟用", bool, False)
        self.single_secret = ConfigProperty[bool](self, "single_secret", "使用固定的SECRET_KEY", bool, False)


debug = DebugConfig(config)


class AccountConfig(ConfigCategory):
    def __init__(self, data: dict):
        super().__init__(data, "account", "帳號系統設定")
        self.signup = ConfigProperty[bool](self, "signup", "是否開放註冊", bool, True)


account = AccountConfig(config)


def init():
    pass
