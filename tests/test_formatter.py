from planner.formatter import (
    split_codigo_disciplina,
    split_horario_sala,
    horario_to_sigaa,
    format_data,
)


def test_split_codigo_disciplina():
    assert split_codigo_disciplina("CIN0130- SISTEMAS DIGITAIS") == ("CIN0130", "SISTEMAS DIGITAIS")
    assert split_codigo_disciplina("CIN0130 - SISTEMAS") == ("CIN0130", "SISTEMAS")
    assert split_codigo_disciplina("CIN0130 - – INTRODUÇÃO À COMPUTAÇÃO") == (
        "CIN0130",
        "INTRODUÇÃO À COMPUTAÇÃO",
    )
    assert split_codigo_disciplina("NOFORMAT") == ("", "NOFORMAT")


def test_split_horario_sala():
    horario, sala = split_horario_sala("seg. 07:00-07:50 (LAB101) / ter. 08:00-08:50 (LAB101)")
    assert "seg." in horario
    assert "ter." in horario
    assert sala == "LAB101"


def test_horario_to_sigaa_simple():
    code = horario_to_sigaa("seg. 07:00-08:50")
    assert "2M23" in code


def test_format_data_filters_header():
    rows = [
        ["Órgão ofertante", "Período", "Turma", "Disciplina", "Docente", "Horário"],
        ["Período: blah"],
        ["CIN", "", "1", "CIN0130- SISTEMAS", "Prof", "seg. 07:00-07:50"],
    ]
    courses = format_data(rows)
    assert len(courses) == 1
    assert courses[0].orgao == "CIN"
    assert courses[0].codigo == "CIN0130"


def test_format_data_with_period_column_layout():
    rows = [
        [
            "Órgão ofertante",
            "Período",
            "Turma",
            "Disciplina",
            "Docente (s)",
            "Horário (Sala/Lab)",
        ],
        [
            "CC",
            "",
            "",
            "CIN0168 - Fundamentos de Teste de Software",
            "Paola Rodrigues de Godoy Accioly",
            "seg. 10:00-11:50 (E122) / qua. 08:00-09:50 (E122)",
        ],
    ]
    courses = format_data(rows)
    assert len(courses) == 1
    assert courses[0].codigo == "CIN0168"
    assert courses[0].name == "Fundamentos de Teste de Software"


def test_format_data_without_period_column_layout():
    rows = [
        ["Órgão ofertante", "Turma", "Disciplina", "Docente (s)", "Horário (Sala/Lab)"],
        [
            "CC",
            "A",
            "CIN0130 - SISTEMAS DIGITAIS",
            "Stefan Blawid",
            "seg. 10:00-11:50 (E112)",
        ],
    ]
    courses = format_data(rows)
    assert len(courses) == 1
    assert courses[0].codigo == "CIN0130"
