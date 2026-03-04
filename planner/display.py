from datetime import time

from colorama import Fore, Style
from tabulate import tabulate

from .models import ALL_TIMECODES, Course, Schedule, DAY_CODES, TimeCode


def _status(course: Course, schedule: Schedule) -> tuple[str, str]:
    course_key = course.key()
    if any(
        occupant == course_key
        for tc in course.timecodes
        if (occupant := schedule.get(str(tc))) is not None
    ):
        return Fore.YELLOW, "Selecionada"
    if all(schedule.get(str(tc)) is None for tc in course.timecodes):
        return Fore.GREEN, "Disponível"
    return Fore.RED, "Indisponível"


def print_table(courses: list[Course], schedule: Schedule, title: str | None = None) -> None:
    courses = list(courses)
    if not courses:
        print(f"Nenhum resultado encontrado{f' para: {title}' if title else ''}.")
        return
    if title:
        print(f"\n{title}\n" + "-" * len(title))

    def row(i: int, c: Course) -> list[str]:
        color, status = _status(c, schedule)

        def col(s: str) -> str:
            return f"{color}{s}{Style.RESET_ALL}"

        return [
            col(str(i)),
            col(c.orgao[:10] + "…" if len(c.orgao) > 11 else c.orgao),
            col(c.codigo),
            col(c.turma),
            col(c.name[:35] + "…" if len(c.name) > 36 else c.name),
            col(c.docente[:15] + "…" if len(c.docente) > 16 else c.docente),
            col(c.horario),
            col(status),
        ]

    headers = ["#", "Curso", "Código", "Turma", "Disciplina", "Docente", "Horário", "Status"]
    print(
        tabulate([row(i + 1, c) for i, c in enumerate(courses)], headers=headers, tablefmt="simple")
    )


def print_schedule(schedule: Schedule) -> None:
    day_slots: dict[str, dict[time, str]] = {name: {} for name in DAY_CODES.values()}
    for key, course in schedule.items():
        if course is None:
            continue
        tc = TimeCode.parse(key)
        day = DAY_CODES.get(tc.day)
        if day:
            t = tc.time
            existing = day_slots[day].get(t)
            codigo, _turma, _orgao = course
            day_slots[day][t] = f"{existing}, {codigo}" if existing else codigo

    all_times = sorted({tc.time for tc in ALL_TIMECODES})
    rows = [
        [t.strftime("%H:%M")] + [day_slots[day].get(t, "-") for day in DAY_CODES.values()]
        for t in all_times
    ]

    print("Cronograma\n----------")
    print(
        tabulate(
            rows, headers=["Hora"] + list(DAY_CODES.values()), tablefmt="github", stralign="center"
        )
    )
