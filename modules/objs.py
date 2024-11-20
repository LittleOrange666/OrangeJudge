from dataclasses import dataclass, is_dataclass, field, asdict
from enum import Enum


def _convert_value(obj):
    if isinstance(obj, Enum):
        return obj.value
    return obj


def _custom_asdict_factory(data):
    return dict((k, _convert_value(v)) for k, v in data)


def as_dict(obj) -> dict:
    return asdict(obj, dict_factory=_custom_asdict_factory)


def is_enum(obj):
    return issubclass(obj, Enum)


def _resolve(val, tp, e):
    if e:
        if isinstance(val, str):
            return tp[val]
    else:
        if isinstance(val, dict):
            return tp(**val)
    return val


def _resolve_r(val, tp, e, t):
    if t == 0:
        return _resolve(val, tp, e)
    elif t == 1:
        return [_resolve(v, tp, e) for v in val]
    elif t == 2:
        return {k: _resolve(v, tp, e) for k, v in val.items()}


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
        arr_l = []
        # Collect all attributes that are annotated as dataclasses or Enums
        for k, v in namespace["__annotations__"].items():
            if is_dataclass(v):
                arr_l.append((k, v, False, 0))
            elif is_enum(v):
                arr_l.append((k, v, True, 0))
            elif hasattr(v, "__origin__"):
                if v.__origin__ is list and len(v.__args__) == 1:
                    if is_dataclass(v.__args__[0]):
                        arr_l.append((k, v.__args__[0], False, 1))
                    elif is_enum(v.__args__[0]):
                        arr_l.append((k, v.__args__[0], True, 1))
                elif v.__origin__ is dict and len(v.__args__) == 2:
                    if is_dataclass(v.__args__[1]):
                        arr_l.append((k, v.__args__[1], False, 2))
                    elif is_enum(v.__args__[1]):
                        arr_l.append((k, v.__args__[1], True, 2))
        arr = tuple(arr_l)

        def _the__post_init__(obj):
            """
            Custom __post_init__ method to initialize nested dataclasses from dictionaries and enums from strings.

            Args:
                obj: The instance of the class being initialized.
            """
            for key, value, e, t in arr:
                setattr(obj, key, _resolve_r(getattr(obj, key), value, e, t))

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


class CodecheckerMode(Enum):
    disabled = "disabled"
    public = "public"
    private = "private"


class ProgramType(Enum):
    my = "my"
    default = "default"


class GenType(Enum):
    sol = "sol"
    gen = "gen"


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
    """
    A dataclass representing the data of a contest.

    Attributes:
        name (str): The name of the contest.
        users (list[str]): A list of users participating in the contest.
        problems (dict[str, ContestProblem]): A dictionary of problems in the contest.
        start (int): The start time of the contest.
        elapsed (int): The duration of the contest.
        type (ContestType): The type of the contest (e.g., ICPC, IOI).
        can_register (bool): Indicates if registration is allowed.
        standing (StandingsData): The standings data of the contest.
        pretest (PretestType): The type of pretest used in the contest.
        practice (PracticeType): The type of practice allowed in the contest.
        participants (list[str]): A list of participants in the contest.
        virtual_participants (dict[str, str]): A dictionary of virtual participants.
        penalty (int): The penalty time in minutes.
    """
    name: str = "unknown"
    users: list[str] = field(default_factory=list)
    problems: dict[str, ContestProblem] = field(default_factory=dict)
    start: int = 0
    elapsed: int = 0
    type: ContestType = ContestType.icpc
    can_register: bool = False
    standing: StandingsData = field(default_factory=StandingsData)
    pretest: PretestType = PretestType.no
    practice: PracticeType = PracticeType.no
    participants: list[str] = field(default_factory=list)
    virtual_participants: dict[str, int] = field(default_factory=dict)
    penalty: int = 20


@dataclass
class Statement:
    main: str = ""
    input: str = ""
    output: str = ""
    scoring: str = ""
    interaction: str = ""


@dataclass
class TestcaseGroup:
    score: int = 100
    rule: str = "min"
    dependency: list[str] = field(default_factory=list)


@dataclass
class Testcase:
    in_file: str
    out_file: str
    group: str = "default"
    uncompleted: bool = False
    sample: bool = False
    pretest: bool = False


@dataclass
class ProgramFile:
    name: str
    type: str


@dataclass
class ProgramPtr(metaclass=DataMeta):
    name: str
    type: ProgramType


@dataclass
class ManualSample:
    in_txt: str
    out_txt: str


@dataclass
class GenGroup(metaclass=DataMeta):
    file1: str
    file2: str
    type: GenType
    group: str = "default"
    cmds: list[str] = field(default_factory=list)
    state: str = "未更新"


@dataclass
class ProblemInfo(metaclass=DataMeta):
    name: str = "unknown"
    timelimit: str = "1000"
    memorylimit: str = "256"
    testcases: list[Testcase] = field(default_factory=list)
    users: list[str] = field(default_factory=list)
    statement: Statement = field(default_factory=Statement)
    files: list[ProgramFile] = field(default_factory=list)
    checker_source: ProgramPtr = field(default_factory=lambda: ProgramPtr("unknown", ProgramType.default))
    is_interact: bool = False
    groups: dict[str, TestcaseGroup] = field(default_factory=lambda: {"default": TestcaseGroup()})
    interactor_source: str = "unknown"
    manual_samples: list[ManualSample] = field(default_factory=list)
    codechecker_source: str = "unknown"
    codechecker_mode: CodecheckerMode = CodecheckerMode.disabled
    languages: dict[str, bool] = field(default_factory=dict)
    public_testcase: bool = False
    public_checker: bool = False
    gen_groups: list[GenGroup] = field(default_factory=list)
    runner_source: dict[str, str] = field(default_factory=dict)
    runner_enabled: bool = False
    library: list[str] = field(default_factory=list)
