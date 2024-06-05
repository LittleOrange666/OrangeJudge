import yaml


class ConfigError(Exception):
    pass


with open("config.yaml", "r") as f:
    config = yaml.load(f, yaml.loader.SafeLoader)
print("config=", config)


def get(path: str):
    cur = config
    for key in path.split("."):
        cur = cur[key]
    return cur


def verify(path: str, _type: type):
    if not isinstance(get(path), _type):
        raise ConfigError(f"{path} is not of type {_type.__name__}")


def verify_int(path: str):
    verify(path, int)


def verify_str(path: str):
    verify(path, str)


def verify_bool(path: str):
    verify(path, bool)


def verify_list(path: str):
    verify(path, list)


def verify_dict(path: str):
    verify(path, dict)


def verify_float(path: str):
    verify(path, float)


verify_dict("smtp")
verify_str("smtp.host")
verify_int("smtp.port")
verify_str("smtp.user")
verify_str("smtp.password")
verify_int("server.port")


def init():
    pass