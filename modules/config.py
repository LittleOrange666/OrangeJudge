from enum import Enum
from typing import Generic, TypeVar, Type

import yaml

T = TypeVar('T')


class ConfigError(Exception):
    pass


with open("config.yaml") as f:
    config = yaml.load(f, yaml.loader.SafeLoader)


# print("config=", config)


def save_config():
    with open("config.yaml", "w") as file:
        yaml.dump(config, file)


class ConfigCategory:
    """
    A class representing a category of configuration settings.

    This class is responsible for managing a specific section of the configuration,
    identified by a key. It initializes the configuration data, validates its structure,
    and sets up any ConfigProperty instances defined in the class.

    Attributes:
        key (str): The key identifying this category in the configuration.
        name (str): A human-readable name for this category.
        data (dict): The configuration data for this category.
        source (dict): The entire configuration data structure.

    Raises:
        ConfigError: If the data for the given key is not a dictionary.
    """

    def __init__(self, data: dict, key: str, name: str):
        """
        Initialize a new ConfigCategory instance.

        Args:
            data (dict): The entire configuration data structure.
            key (str): The key identifying this category in the configuration.
            name (str): A human-readable name for this category.

        Raises:
            ConfigError: If the data for the given key is not a dictionary.
        """
        self.key = key
        self.name = name
        if key not in data:
            data[key] = {}
        if not isinstance(data[key], dict):
            raise ConfigError(f"'{key}' is not a dict")
        self.data = data[key]
        self.source = data
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, ConfigProperty):
                v.init(self, k)


class ConfigProperty(Generic[T]):
    """
    A generic class representing a configuration property.

    This class is designed to manage individual configuration properties,
    providing type checking, default values, and automatic saving of changes.

    Attributes:
        __slots__ (tuple): Defines the allowed attributes for memory optimization.
    """

    __slots__ = ("_value", "_name", "_key", "_type", "_parent", "_default")

    def __init__(self, name: str, _type: Type[T], _default: T):
        """
        Initialize a new ConfigProperty instance.

        Args:
            name (str): A human-readable name for the property.
            _type (Type[T]): The expected type of the property value.
            _default (T): The default value for the property.
        """
        self._key = None
        self._name = name
        self._type = _type
        self._default = _default
        self._value = None
        self._parent = None

    def init(self, parent: ConfigCategory, key: str):
        """
        Initialize the property with its parent category and key.

        This method sets up the property, validates its type, and handles
        Enum types specially. It also ensures the property exists in the
        parent's data, creating it with the default value if necessary.

        Args:
            parent (ConfigCategory): The parent configuration category.
            key (str): The key identifying this property in the parent's data.

        Raises:
            ConfigError: If the property value doesn't match the expected type.
        """
        if key not in parent.data:
            parent.data[key] = self._default
        if issubclass(self._type, Enum):
            if not isinstance(parent.data[key], str):
                raise ConfigError(f"'{parent.key}.{key}' is not a string")
            elif parent.data[key] not in self._type._member_names_:
                raise ConfigError(
                    f"'{parent.key}.{key}' ('{parent.data[key]}') is not a valid {self._type.__name__}")
            self._value: T = self._type[parent.data[key]]
        else:
            if not isinstance(parent.data[key], self._type):
                raise ConfigError(f"'{parent.key}.{key}' is not a {self._type.__name__}")
            self._value: T = parent.data[key]
        self._key = key
        self._parent = parent
        self._type = self._type

    def __get__(self, instance: ConfigCategory, cls: type) -> T:
        """
        Getter method for the property value.

        Args:
            instance (ConfigCategory): The instance that this property belongs to.
            cls (type): The class that this property is defined on.

        Returns:
            T: The current value of the property.
        """
        return self._value

    def __set__(self, instance: ConfigCategory, new_val: T):
        """
        Setter method for the property value.

        This method updates the property value, updates the parent's data,
        and saves the configuration changes.

        Args:
            instance (ConfigCategory): The instance that this property belongs to.
            new_val (T): The new value to set for the property.
        """
        self._value = new_val
        if issubclass(self._type, Enum):
            self._parent.data[self._key] = new_val.name
        else:
            self._parent.data[self._key] = new_val
        save_config()


class SmtpConfig(ConfigCategory):
    host = ConfigProperty[str]("SMTP伺服器", str, "smtp.gmail.com")
    port = ConfigProperty[int]("SMTP伺服器連接埠", int, 587)
    user = ConfigProperty[str]("SMTP使用者名稱(email)", str, "user@gmail.com")
    password = ConfigProperty[str]("SMTP使用者密碼", str, "password")
    enabled = ConfigProperty[bool]("SMTP是否啟用", bool, False)
    limit = ConfigProperty[str]("驗證碼頻率限制", str, "1 per 20 second")

    def __init__(self, data: dict):
        super().__init__(data, "smtp", "SMTP設定")


class ServerConfig(ConfigCategory):
    port = ConfigProperty[int]("此伺服器的連接埠", int, 8080)
    workers = ConfigProperty[int]("WSGI並行數量", int, 4)
    timeout = ConfigProperty[int]("WSGI超時時間", int, 120)
    limits = ConfigProperty[list[str]]("請求頻率限制列表", list,
                                       ["30 per 30 second", "3 per 1 second"])
    file_limit = ConfigProperty[str]("檔案下載頻率限制", str, "30 per 5 second")

    def __init__(self, data: dict):
        super().__init__(data, "server", "伺服器設定")


class JudgeConfig(ConfigCategory):
    workers = ConfigProperty[int]("評測系統並行數量", int, 1)
    limit = ConfigProperty[str]("提交頻率限制", str, "1 per 10 second")
    file_size = ConfigProperty[int]("檔案大小限制(KB)", int, 100)

    def __init__(self, data: dict):
        super().__init__(data, "judge", "評測系統設定")


class DebugConfig(ConfigCategory):
    log = ConfigProperty[bool]("除錯紀錄是否啟用", bool, False)
    single_secret = ConfigProperty[bool]("使用固定的SECRET_KEY", bool, False)

    def __init__(self, data: dict):
        super().__init__(data, "debug", "除錯設定")


class AccountConfig(ConfigCategory):
    signup = ConfigProperty[bool]("是否開放註冊", bool, True)

    def __init__(self, data: dict):
        super().__init__(data, "account", "帳號系統設定")


smtp = SmtpConfig(config)
server = ServerConfig(config)
judge = JudgeConfig(config)
debug = DebugConfig(config)
account = AccountConfig(config)
save_config()


def init():
    pass
