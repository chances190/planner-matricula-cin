import difflib
import json
import os
import re
import unicodedata
from typing import cast

from .models import (
    Course,
    CourseKey,
    DAY_CODES,
    PERIOD_NAMES,
    Schedule,
    TimeCode,
    empty_schedule,
)


def _slot_label(tc: TimeCode) -> str:
    return f"{DAY_CODES.get(tc.day, '?')} {PERIOD_NAMES[tc.shift]} {tc.time.strftime('%H:%M')}"


class CourseScheduler:
    def __init__(
        self, courses_file: str = "disciplinas.jsonl", schedule_file: str = "schedule.json"
    ) -> None:
        self.courses_file = courses_file
        self.schedule_file = schedule_file
        self.courses: list[Course] = []
        self.schedule: Schedule = empty_schedule()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.courses_file):
            raise FileNotFoundError(f"Courses file not found: {self.courses_file}")

        if not self.courses_file.endswith(".jsonl"):
            raise ValueError("Courses file must be a .jsonl file")

        with open(self.courses_file, encoding="utf-8") as f:
            self.courses = [Course.from_dict(json.loads(line)) for line in f if line.strip()]

        if os.path.exists(self.schedule_file):
            with open(self.schedule_file, encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("Schedule file must be a JSON object")

            loaded_dict = cast(dict[str, object], loaded)
            normalized = empty_schedule()
            for key, value in loaded_dict.items():
                if key not in normalized:
                    continue
                if value is None:
                    normalized[key] = None
                    continue
                if not isinstance(value, list):
                    raise ValueError(
                        f"Invalid schedule entry for slot {key!r}: expected [codigo, turma, orgao]"
                    )
                entry = cast(list[object], value)
                if len(entry) != 3:
                    raise ValueError(
                        f"Invalid schedule entry for slot {key!r}: expected [codigo, turma, orgao]"
                    )
                normalized[key] = (str(entry[0]), str(entry[1]), str(entry[2]))
            self.schedule = normalized

    def _save(self) -> None:
        with open(self.schedule_file, "w", encoding="utf-8") as f:
            json.dump(self.schedule, f, ensure_ascii=False, indent=2)

    def is_selected(self, course: Course) -> bool:
        course_key = course.key()
        return any(
            occupant == course_key
            for tc in course.timecodes
            if (occupant := self.schedule.get(str(tc))) is not None
        )

    def is_available(self, course: Course) -> bool:
        return all(self.schedule.get(str(tc)) is None for tc in course.timecodes)

    def conflicts(self, course: Course) -> dict[TimeCode, CourseKey]:
        return {
            tc: occupant
            for tc in course.timecodes
            if (occupant := self.schedule.get(str(tc))) is not None
        }

    def add_course(self, course: Course) -> bool:
        if self.is_selected(course):
            print(f"'{course.name}' já está no cronograma.")
            return False
        c = self.conflicts(course)
        if c:
            print(f"Conflitos para '{course.name}' ({course.codigo}) turma {course.turma!r}:")
            for tc, occupant in c.items():
                codigo, turma, _orgao = occupant
                print(f"  → {codigo} turma {turma!r} em {_slot_label(tc)}")
            print("Não é possível adicionar devido aos conflitos.")
            return False
        course_key = course.key()
        for tc in course.timecodes:
            self.schedule[str(tc)] = course_key
        self._save()
        print(f"'{course.name}' ({course.codigo}) adicionada.")
        return True

    def remove_course(self, course: Course) -> bool:
        if not self.is_selected(course):
            print(f"'{course.name}' não está no cronograma.")
            return False
        course_key = course.key()
        for tc in course.timecodes:
            occupant = self.schedule.get(str(tc))
            if occupant == course_key:
                self.schedule[str(tc)] = None
        self._save()
        print(f"'{course.name}' ({course.codigo}) removida.")
        return True

    def find_by_code(self, code: str) -> list[Course]:
        code = code.strip().upper()
        return [c for c in self.courses if c.codigo.upper() == code]

    def find_by_name(self, query: str, limit: int = 10) -> list[Course]:
        def norm(s: str) -> str:
            return (
                unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode().upper().strip()
            )

        q = norm(query)
        exact = [c for c in self.courses if q in norm(c.name)]
        if exact:
            return exact[:limit]
        scored = sorted(
            ((difflib.SequenceMatcher(None, q, norm(c.name)).ratio(), c) for c in self.courses),
            key=lambda x: x[0],
            reverse=True,
        )
        return [c for score, c in scored[:limit] if score > 0.3]

    def find_by_time_code(self, time_code: str) -> tuple[list[Course], str | None]:
        m = re.fullmatch(r"([2-7])([MTN])([1-6]+)", time_code, re.IGNORECASE)
        if not m:
            return [], f"Código inválido: {time_code}. Use 'dia[2-7]período[M/T/N]horas[1-6]'"
        day, shift, hours = m.groups()
        requested = {TimeCode(day, shift.upper(), int(h)) for h in hours}
        return [c for c in self.courses if c.timecodes & requested], None

    def all_courses(self) -> list[Course]:
        return sorted(self.courses, key=lambda c: c.name.lower())

    def selected_courses(self) -> list[Course]:
        return [c for c in self.courses if self.is_selected(c)]
