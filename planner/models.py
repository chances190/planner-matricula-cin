import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import time
from typing import TypedDict


CourseKey = tuple[str, str, str]


class CourseData(TypedDict):
    orgao: str
    turma: str
    codigo: str
    name: str
    docente: str
    horario: str
    sala: str


DAY_CODES: dict[str, str] = {
    "2": "Segunda",
    "3": "Terça",
    "4": "Quarta",
    "5": "Quinta",
    "6": "Sexta",
    "7": "Sábado",
}

PERIOD_NAMES: dict[str, str] = {"M": "Manhã", "T": "Tarde", "N": "Noite"}

SLOT_TIMES: dict[tuple[str, int], time] = {
    ("M", 1): time(6, 0),
    ("M", 2): time(7, 0),
    ("M", 3): time(8, 0),
    ("M", 4): time(9, 0),
    ("M", 5): time(10, 0),
    ("M", 6): time(11, 0),
    ("T", 1): time(12, 0),
    ("T", 2): time(13, 0),
    ("T", 3): time(14, 0),
    ("T", 4): time(15, 0),
    ("T", 5): time(16, 0),
    ("T", 6): time(17, 0),
    ("N", 1): time(18, 0),
    ("N", 2): time(18, 50),
    ("N", 3): time(19, 40),
    ("N", 4): time(20, 30),
    ("N", 5): time(21, 20),
    ("N", 6): time(22, 10),
}


@dataclass(frozen=True)
class TimeCode:
    day: str  # "2"–"7"
    shift: str  # "M", "T", "N"
    number: int  # 1–6

    def __str__(self) -> str:
        return f"{self.day}{self.shift}{self.number}"

    @property
    def time(self) -> time:
        return SLOT_TIMES[(self.shift, self.number)]

    @classmethod
    def parse(cls, s: str) -> "TimeCode":
        m = re.fullmatch(r"([2-7])([MTN])([1-6])", s.strip())
        if not m:
            raise ValueError(f"Invalid TimeCode: {s!r}")
        return cls(m.group(1), m.group(2), int(m.group(3)))


def parse_timecodes(horario: str) -> frozenset[TimeCode]:
    codes: set[TimeCode] = set()
    for part in horario.split():
        m = re.fullmatch(r"([2-7])([MTN])([1-6]+)", part)
        if m:
            day, shift, numbers = m.groups()
            codes.update(TimeCode(day, shift, int(n)) for n in numbers)
    return frozenset(codes)


ALL_TIMECODES: list[TimeCode] = [
    TimeCode(day, shift, n) for day in DAY_CODES for shift in PERIOD_NAMES for n in range(1, 7)
]

# Schedule maps every slot key "2M1" → course identity {codigo, turma, orgao} or None
Schedule = dict[str, CourseKey | None]


def empty_schedule() -> Schedule:
    return {str(tc): None for tc in ALL_TIMECODES}


@dataclass
class Course:
    orgao: str
    turma: str
    codigo: str
    name: str
    docente: str
    horario: str
    sala: str
    timecodes: frozenset[TimeCode] = field(init=False)

    def __post_init__(self):
        self.timecodes = parse_timecodes(self.horario)

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Course) and self.key() == other.key()

    def key(self) -> CourseKey:
        return (self.codigo, self.turma, self.orgao)

    def to_dict(self) -> CourseData:
        return {
            "orgao": self.orgao,
            "turma": self.turma,
            "codigo": self.codigo,
            "name": self.name,
            "docente": self.docente,
            "horario": self.horario,
            "sala": self.sala,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, str]) -> "Course":
        return cls(
            orgao=d.get("orgao", ""),
            turma=d.get("turma", ""),
            codigo=d.get("codigo", ""),
            name=d.get("name", ""),
            docente=d.get("docente", ""),
            horario=d.get("horario", ""),
            sala=d.get("sala", ""),
        )

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "Course":
        return cls(
            orgao=row.get("órgão ofertante", "").strip(),
            turma=row.get("turma", "").strip(),
            codigo=row.get("código", "").strip(),
            name=row.get("disciplina", "").strip(),
            docente=row.get("docente", "").strip(),
            horario=row.get("horário", "").strip(),
            sala=row.get("sala/lab", "").strip(),
        )
