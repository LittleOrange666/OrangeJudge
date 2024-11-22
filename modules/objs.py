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
        if isinstance(val, list):
            return tp(*val)
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
        if len(bases):
            return super().__new__(cls, name, bases, namespace)
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
        if "__post_init__" in namespace:
            _old_post_init = namespace["__post_init__"]

            def _the__post_init__(obj):
                """
                Custom __post_init__ method to initialize nested dataclasses from dictionaries and enums from strings.

                Args:
                    obj: The instance of the class being initialized.
                """
                for key, value, e, t in arr:
                    setattr(obj, key, _resolve_r(getattr(obj, key), value, e, t))
                _old_post_init(obj)

            namespace["__post_init__"] = _the__post_init__
        else:
            def _the__post_init__(obj):
                """
                Custom __post_init__ method to initialize nested dataclasses from dictionaries and enums from strings.

                Args:
                    obj: The instance of the class being initialized.
                """
                for key, value, e, t in arr:
                    setattr(obj, key, _resolve_r(getattr(obj, key), value, e, t))

            namespace["__post_init__"] = _the__post_init__

        # Add the custom __post_init__ method to the class namespace
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
        judger_log (str): The log from the judger, default is an empty string.
        seccomp_info (str): The seccomp information, default is an empty string.
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
    judger_log: str = ""
    seccomp_info: str = ""


@dataclass
class InteractResult(metaclass=DataMeta):
    """
    A dataclass representing an interaction judge result.

    Attributes:
        result (Result): The result of the main program.
        interact_result (Result): The result of the interaction program.
    """
    result: Result
    interact_result: Result


@dataclass
class CallResult:
    """
    A dataclass representing the result of a system call.

    Attributes:
        stdout (str): The standard output from the system call.
        stderr (str): The standard error output from the system call.
        return_code (int): The return code of the system call.
    """
    stdout: str
    stderr: str
    return_code: int


class ContestType(Enum):
    """
    An enumeration representing the type of contest.

    Attributes:
        icpc (str): Represents an ICPC-style contest.
        ioi (str): Represents an IOI-style contest.
    """
    icpc = "icpc"
    ioi = "ioi"


class PracticeType(Enum):
    """
    An enumeration representing the setting of practice.

    Attributes:
        private (str): Represents practice is allowed for registered users.
        public (str): Represents practice is allowed for everyone.
        no (str): Represents practice is not allowed.
    """
    private = "private"
    public = "public"
    no = "no"


class PretestType(Enum):
    """
    An enumeration representing the type of pretest.

    Attributes:
        all (str): Represents all submissions will be rejudged.
        last (str): Represents the last submission will be rejudged.
        no (str): Represents pretests is disabled.
        fake_all (str): Represents all submissions are counted into score, but hide results before ended.
        fake_last (str): Represents the last submission is counted into score, and hide results before ended.
    """
    all = "all"
    last = "last"
    no = "no"
    fake_all = "fake_all"
    fake_last = "fake_last"


class CodecheckerMode(Enum):
    """
    An enumeration representing the mode of the code checker.

    Attributes:
        disabled (str): Represents the code checker is disabled.
        public (str): Represents the code checker result is public.
        private (str): Represents the code checker result is private.
    """
    disabled = "disabled"
    public = "public"
    private = "private"


class ProgramType(Enum):
    """
    An enumeration representing the type of program.

    Attributes:
        my (str): Represents a user-defined program.
        default (str): Represents a program from testlib.
    """
    my = "my"
    default = "default"


class GenType(Enum):
    """
    An enumeration representing the method of generating answer.

    Attributes:
        sol (str): Represents using a solution to generating answer.
        gen (str): Represents using another generator to generating answer.
    """
    sol = "sol"
    gen = "gen"


class TestcaseRule(Enum):
    """
    An enumeration representing the scoring rule for test cases.

    Attributes:
        min (str): Represents using the minimum score.
        avg (str): Represents using the average score.
    """
    min = "min"
    avg = "avg"


class StatementType(Enum):
    """
    An enumeration representing the type of statement.

    Attributes:
        md (str): Represents a Markdown statement.
        latex (str): Represents a LaTeX statement.
    """
    md = "md"
    latex = "latex"


class TaskResult(Enum):
    """
    An enumeration representing the possible results of a task.

    Attributes:
        OK (str): Represents a successful task.
        WA (str): Represents a wrong answer.
        TLE (str): Represents a time limit exceeded.
        MLE (str): Represents a memory limit exceeded.
        RE (str): Represents a runtime error.
        CE (str): Represents a compilation error.
        JE (str): Represents a judge error.
        RF (str): Represents a restricted function error.
        FAIL (str): Represents a judge failed.
        PARTIAL (str): Represents a partially correct task.
        PENDING (str): Represents a pending task.
        PE (str): Represents a presentation error.
        POINTS (str): Represents a points task.
        DIRT (str): Represents a dirt?.
        OLE (str): Represents an output limit exceeded.
        SKIP (str): Represents a skipped task.
    """
    OK = "OK"
    WA = "WA"
    TLE = "TLE"
    MLE = "MLE"
    RE = "RE"
    CE = "CE"
    JE = "JE"
    RF = "RF"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"
    PE = "PE"
    POINTS = "POINTS"
    DIRT = "DIRT"
    OLE = "OLE"
    SKIP = "SKIP"

    def is_zero(self):
        return self not in (TaskResult.OK, TaskResult.PARTIAL, TaskResult.POINTS, TaskResult.PENDING, TaskResult.SKIP)

    def css_class(self):
        match self:
            case TaskResult.OK:
                return "table-success"
            case TaskResult.WA:
                return "table-danger"
            case TaskResult.MLE:
                return "table-warning"
            case TaskResult.TLE:
                return "table-info"
            case TaskResult.OLE:
                return "table-secondary"
            case TaskResult.RE:
                return "table-secondary"
            case _:
                return "table-secondary"


@dataclass
class StandingsData:
    """
    A dataclass representing the standings data.

    Attributes:
        public (bool): Indicates if the standings are public.
        start_freeze (int): The start time of the freeze period.
        end_freeze (int): The end time of the freeze period.
    """
    public: bool = True
    start_freeze: int = 0
    end_freeze: int = 0


@dataclass
class ContestProblem(metaclass=DataMeta):
    """
    A dataclass representing a contest problem.

    Attributes:
        pid (str): The problem ID.
        name (str): The name of the problem.
    """
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
class Statement(metaclass=DataMeta):
    """
    A dataclass representing the statement of a problem.

    Attributes:
        main (str): The main statement.
        input (str): The input description.
        output (str): The output description.
        scoring (str): The scoring description.
        interaction (str): The interaction description.
        type (StatementType): The type of the statement.
    """
    main: str = ""
    input: str = ""
    output: str = ""
    scoring: str = ""
    interaction: str = ""
    type: StatementType = StatementType.md


@dataclass
class TestcaseGroup(metaclass=DataMeta):
    """
    A dataclass representing a group of test cases.

    Attributes:
        score (int): The score for the group.
        rule (TestcaseRule): The rule for scoring the group.
        dependency (list[str]): The dependencies of the group.
    """
    score: int = 100
    rule: TestcaseRule = TestcaseRule.min
    dependency: list[str] = field(default_factory=list)


@dataclass
class GroupResult(metaclass=DataMeta):
    """
    A dataclass representing the result of a group of test cases.

    Attributes:
        result (TaskResult): The result of the group.
        time (int): The maximum time used in the group.
        mem (int): The maximum memory used in group.
        gainscore (float): The score gained by the group.
        css_class (str): The CSS class for the group result.
    """
    result: TaskResult
    time: int
    mem: int
    gainscore: float
    css_class: str = ""


@dataclass
class RunningTestcaseGroup(metaclass=DataMeta):
    """
    A dataclass record a group of test cases while judging.

    Attributes:
        score (int): The score for the group.
        rule (TestcaseRule): The rule for scoring the group.
        dependency (list[str]): The dependencies of the group.
        result (str): The result of the group.
        time (int): The maximum time used in the group.
        mem (int): The maximum memory used in group.
        gainscore (int): The score gained by the group.
        cnt (int): The count of test cases in the group.
    """
    score: int = 100
    rule: TestcaseRule = TestcaseRule.min
    dependency: list[str] = field(default_factory=list)
    result: TaskResult = TaskResult.OK
    time: int = 0
    mem: int = 0
    gainscore: int = 0
    cnt: int = 0
    target_cnt: int = 0

    def to_result(self) -> GroupResult:
        """
        Convert the current `RunningTestcaseGroup` instance to a `GroupResult` instance.

        Returns:
            GroupResult: The result of the test case group.
        """
        res = self.result
        if self.cnt < self.target_cnt:
            res = TaskResult.PENDING
        return GroupResult(result=res, time=self.time, mem=self.mem, gainscore=self.gainscore)


@dataclass
class Testcase:
    """
    A dataclass representing a test case.

    Attributes:
        in_file (str): The input file for the test case.
        out_file (str): The output file for the test case.
        group (str): The group of the test case.
        uncompleted (bool): Indicates if the test case is uncompleted.
        sample (bool): Indicates if the test case is a sample.
        pretest (bool): Indicates if the test case is in pretest.
        gen (bool): Indicates if the test case is generated.
    """
    in_file: str
    out_file: str
    group: str = "default"
    uncompleted: bool = False
    sample: bool = False
    pretest: bool = False
    gen: bool = False


@dataclass
class ProgramFile:
    """
    A dataclass representing a program file.

    Attributes:
        name (str): The name of the program file.
        type (str): The language of the program file.
    """
    name: str
    type: str


@dataclass
class ProgramPtr(metaclass=DataMeta):
    """
    A dataclass representing a pointer to a program.

    Attributes:
        type (ProgramType): The type of the program.
        name (str): The name of the program.
    """
    type: ProgramType
    name: str


@dataclass
class ExecPtr:
    """
    A dataclass representing a pointer to an executable.

    Attributes:
        name (str): The name of the executable.
        lang (str): The language of the executable.
    """
    name: str = "unknown"
    lang: str = "unknown"


@dataclass
class ManualSample:
    """
    A dataclass representing a manual sample.

    Attributes:
        in_txt (str): The input text of the sample.
        out_txt (str): The output text of the sample.
    """
    in_txt: str
    out_txt: str


@dataclass
class GenGroup(metaclass=DataMeta):
    """
    A dataclass representing a generation group.

    Attributes:
        file1 (str): The first file of the generation group.
        file2 (str): The second file of the generation group.
        type (GenType): The type of the generation group.
        group (str): The group of the generation group.
        cmds (list[str]): The commands for the generation group.
        status (str): The status of the generation group.
    """
    file1: str
    file2: str
    type: GenType
    group: str = "default"
    cmds: list[str] = field(default_factory=list)
    status: str = "未更新"


@dataclass
class ProblemVersion:
    """
    A dataclass representing a version of a problem.

    Attributes:
        description (str): The description of the version.
        time (float): The creation time of the version.
    """
    description: str
    time: float


@dataclass
class ProblemInfo(metaclass=DataMeta):
    """
    A dataclass representing the information of a problem.

    Attributes:
        name (str): The name of the problem.
        timelimit (str): The time limit of the problem.
        memorylimit (str): The memory limit of the problem.
        testcases (list[Testcase]): The list of test cases for the problem.
        testcases_gen (list[Testcase]): The list of generated test cases for the problem.
        users (list[str]): The list of owners for the problem.
        statement (Statement): The statement of the problem.
        files (list[ProgramFile]): The list of program files for the problem.
        checker_source (ProgramPtr): The source of the checker program.
        checker (ExecPtr): The executable of the checker program.
        is_interact (bool): Indicates if the problem is interactive.
        groups (dict[str, TestcaseGroup]): The groups of test cases for the problem.
        interactor_source (str): The source of the interactor program.
        interactor (ExecPtr): The executable of the interactor program.
        manual_samples (list[ManualSample]): The list of manual samples for the problem.
        codechecker_source (str): The source of the code checker program.
        codechecker (ExecPtr): The executable of the code checker program.
        codechecker_mode (CodecheckerMode): The mode of the code checker.
        languages (dict[str, bool]): The languages allowed for the problem.
        public_testcase (bool): Indicates if the test cases are public.
        public_checker (bool): Indicates if the checker is public.
        gen_groups (list[GenGroup]): The list of generation groups for the problem.
        runner_source (dict[str, str]): The source of the runner program.
        runner_enabled (bool): Indicates if the runner is enabled.
        library (list[str]): The list of libraries for the problem.
        versions (list[ProblemVersion]): The list of versions for the problem.
        top_score (int): The top score for the problem.
    """
    name: str = "unknown"
    timelimit: str = "1000"
    memorylimit: str = "256"
    testcases: list[Testcase] = field(default_factory=list)
    testcases_gen: list[Testcase] = field(default_factory=list)
    users: list[str] = field(default_factory=list)
    statement: Statement = field(default_factory=Statement)
    files: list[ProgramFile] = field(default_factory=list)
    checker_source: ProgramPtr = field(default_factory=lambda: ProgramPtr(ProgramType.default, "unknown"))
    checker: ExecPtr = field(default_factory=ExecPtr)
    is_interact: bool = False
    groups: dict[str, TestcaseGroup] = field(default_factory=lambda: {"default": TestcaseGroup()})
    interactor_source: str = "unknown"
    interactor: ExecPtr = field(default_factory=ExecPtr)
    manual_samples: list[ManualSample] = field(default_factory=list)
    codechecker_source: str = "unknown"
    codechecker: ExecPtr = field(default_factory=ExecPtr)
    codechecker_mode: CodecheckerMode = CodecheckerMode.disabled
    languages: dict[str, bool] = field(default_factory=dict)
    public_testcase: bool = False
    public_checker: bool = False
    gen_groups: list[GenGroup] = field(default_factory=list)
    runner_source: dict[str, str] = field(default_factory=dict)
    runner_enabled: bool = False
    library: list[str] = field(default_factory=list)
    versions: list[ProblemVersion] = field(default_factory=list)
    top_score: int = 100

    def update(self, new_data: dict):
        """
        Update the problem information with new data.

        Args:
            new_data (dict): The new data to update the problem information.
        """
        for key in new_data:
            if key in self.__annotations__:
                setattr(self, key, new_data[key])
        self.__post_init__()


@dataclass
class SubmissionData:
    """
    A dataclass representing the data of a submission.

    Attributes:
        infile (str): The input file name.
        outfile (str): The output file name.
        JE (bool): Indicates if there was a judge error.
        log_uuid (str): The UUID for the judge error log.
    """
    infile: str = "in.txt"
    outfile: str = "out.txt"
    JE: bool = False
    log_uuid: str = ""


@dataclass
class TestcaseResult(metaclass=DataMeta):
    """
    A dataclass representing the result of a test case.

    Attributes:
        time (int): The time taken by the test case.
        mem (int): The memory used by the test case.
        result (TaskResult): The result of the test case.
        info (str): Additional information about the test case.
        has_output (bool): Indicates if the test case has output.
        score (float): The score of the test case.
        sample (bool): Indicates if the test case is a sample.
        in_txt (str): The input text of the test case.
        out_txt (str): The output text of the test case.
        ans_txt (str): The answer text of the test case.
        completed (bool): Indicates if the test case is completed.
    """
    result: TaskResult
    info: str
    time: int = 0
    mem: int = 0
    has_output: bool = False
    score: float = 0.0
    sample: bool = False
    in_txt: str = ""
    out_txt: str = ""
    ans_txt: str = ""
    completed: bool = True


@dataclass
class SubmissionResult(metaclass=DataMeta):
    """
    A dataclass representing the result of a submission.

    Attributes:
        results (list[TestcaseResult]): The list of test case results.
        group_results (dict[str, GroupResult]): The dictionary of group results.
        CE (bool): Indicates if there was a compilation error.
        total_score (float): The total score of the submission.
        protected (bool): Indicates if the submission is protected.
    """
    results: list[TestcaseResult] = field(default_factory=list)
    group_results: dict[str, GroupResult] = field(default_factory=dict)
    CE: bool = False
    total_score: float = 0.0
    protected: bool = False
    codechecker_msg: str = ""


class Permission(Enum):
    """
    This enumeration represents different levels of permissions in the OrangeJudge system.

    Attributes:
        root (str): Represents the highest level of permission. It is used for the root user.
        admin (str): Represents the permission level of an administrator.
        make_problems (str): Represents the permission level of a problem maker.
    """
    root = "最高管理者"
    admin = "管理者"
    make_problems = "出題者"
