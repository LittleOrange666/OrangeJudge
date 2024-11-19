from dataclasses import dataclass, is_dataclass, field, asdict
from enum import Enum


def _convert_value(obj):
    if isinstance(obj, Enum):
        return obj.value
    return obj


def _custom_asdict_factory(data):
    return dict((k, _convert_value(v)) for k, v in data)


def as_dict(obj):
    return asdict(obj, dict_factory=_custom_asdict_factory)


class DataMeta(type):
    """
    Metaclass for dataclasses that automatically initializes nested dataclasses and enums from dictionaries and strings.
    """

    def __new__(cls, name, bases, namespace):
        """
        Create a new class with a custom __post_init__ method that initializes nested dataclasses and enums.

        Args:
            cls: The metaclass.
            name: The name of the new class.
            bases: The base classes of the new class.
            namespace: The namespace containing the class attributes and methods.

        Returns:
            The newly created class.
        """
        print(namespace)
        # Collect all attributes that are annotated as dataclasses
        arr = tuple((k, v) for k, v in namespace["__annotations__"].items() if is_dataclass(v))
        # Collect all attributes that are annotated as Enums
        e_arr = tuple((k, v) for k, v in namespace["__annotations__"].items() if issubclass(v, Enum))

        def _the__post_init__(obj):
            """
            Custom __post_init__ method to initialize nested dataclasses from dictionaries and enums from strings.

            Args:
                obj: The instance of the class being initialized.
            """
            for k, v in arr:
                val = getattr(obj, k)
                if isinstance(val, dict):
                    # Initialize the attribute with the dataclass if it is a dictionary
                    setattr(obj, k, v(**val))
            for k, v in e_arr:
                val = getattr(obj, k)
                if isinstance(val, str):
                    # Initialize the attribute with the enum if it is a string
                    setattr(obj, k, v[val])

        # Add the custom __post_init__ method to the class namespace
        namespace["__post_init__"] = _the__post_init__
        namespace["as_dict"] = as_dict
        return super().__new__(cls, name, bases, namespace)


@dataclass
class Result:
    """
    A dataclass representing the result of an judge operation.

    Attributes:
        cpu_time (int): The CPU time in milliseconds.
        real_time (int): The real time in milliseconds.
        memory (int): The memory usage in bytes.
        signal (int): The signal number.
        exit_code (int): The exit code of the operation.
        error (str): The error message, if any.
        result (str): The result message.
        error_id (int): The error identifier.
        result_id (int): The result identifier.
        judger_log (int): The log from the judger, default is an empty string.
    """
    cpu_time: int  # ms
    real_time: int  # ms
    memory: int  # Bytes
    signal: int
    exit_code: int
    error: str
    result: str
    error_id: int
    result_id: int
    judger_log: int = ""


@dataclass
class InteractResult(metaclass=DataMeta):
    result: Result
    interact_result: Result


@dataclass
class CallResult:
    stdout: str
    stderr: str
    return_code: int


class ContestType(Enum):
    icpc = "icpc"
    ioi = "ioi"


class PracticeType(Enum):
    private = "private"
    public = "public"
    no = "no"


class PretestType(Enum):
    all = "all"
    last = "last"
    no = "no"


@dataclass
class StandingsData(metaclass=DataMeta):
    public: bool = True
    start_freeze: int = 0
    end_freeze: int = 0


@dataclass
class ContestProblem(metaclass=DataMeta):
    pid: str = "unknown"
    name: str = "unknown"


@dataclass
class ContestData(metaclass=DataMeta):
    name: str = "unknown"
    users: list[str] = field(default_factory=list)
    problems: dict[str, ContestProblem] = field(default_factory=dict)
    start: int = 0
    elapsed: int = 0
    type: ContestType = ContestType.icpc
    can_register: bool = False
    standing: StandingsData = StandingsData()
    pretest: PretestType = PretestType.no
    practice: PracticeType = PracticeType.no
    participants: list[str] = field(default_factory=list)
    virtual_participants: dict[str, str] = field(default_factory=dict)
    penalty: int = 20
