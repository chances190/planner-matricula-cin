import json
import pytest
from pathlib import Path

from planner.models import Course
from planner.scheduler import CourseScheduler


@pytest.fixture
def tmp_courses(tmp_path):
    f = tmp_path / "courses.jsonl"
    courses = [
        {
            "orgao": "Dept",
            "turma": "1",
            "codigo": "CIN0001",
            "name": "Teste",
            "docente": "Prof",
            "horario": "2M1",
            "sala": "LAB1",
        },
        {
            "orgao": "Dept",
            "turma": "1",
            "codigo": "CIN0002",
            "name": "Outro",
            "docente": "Prof2",
            "horario": "2M1",
            "sala": "LAB2",
        },
    ]
    f.write_text("\n".join(json.dumps(c) for c in courses))
    return f


def test_find_by_code(tmp_courses):
    s = CourseScheduler(str(tmp_courses), str(tmp_courses.parent / "schedule.json"))
    assert len(s.find_by_code("CIN0001")) == 1


def test_conflict_detection(tmp_courses):
    s = CourseScheduler(str(tmp_courses), str(tmp_courses.parent / "schedule.json"))
    c1 = s.find_by_code("CIN0001")[0]
    c2 = s.find_by_code("CIN0002")[0]
    assert s.add_course(c1)
    assert not s.add_course(c2)


def test_remove_course(tmp_courses):
    s = CourseScheduler(str(tmp_courses), str(tmp_courses.parent / "schedule.json"))
    c1 = s.find_by_code("CIN0001")[0]
    s.add_course(c1)
    assert s.remove_course(c1)
    assert not s.is_selected(c1)
