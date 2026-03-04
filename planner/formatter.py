import re
import unicodedata
from collections import defaultdict
from datetime import datetime

from .models import Course, SLOT_TIMES


def split_codigo_disciplina(text: str) -> tuple[str, str]:
    def clean_name(name: str) -> str:
        return re.sub(r"^[\s\-–—:]+", "", name).strip()

    m = re.match(r"([A-Z]{2,}\d{3,})\s*-\s*(.+)", text)
    if m:
        return m.group(1), clean_name(m.group(2))
    parts = text.split(None, 1)
    if len(parts) == 2 and re.match(r"[A-Z]{2,}\d{3,}", parts[0]):
        return parts[0], clean_name(parts[1])
    return "", clean_name(text)


def split_horario_sala(horario: str) -> tuple[str, str]:
    salas = list(dict.fromkeys(re.findall(r"\(([^)]+)\)", horario)))
    horario_clean = re.sub(r"\([^)]*\)", "", horario)
    horario_clean = re.sub(r"\s+/\s+", " / ", horario_clean)
    horario_clean = re.sub(r"\s+", " ", horario_clean).strip()
    return horario_clean, " ".join(salas)


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII").lower()


_DAY_MAP = {"seg": "2", "ter": "3", "qua": "4", "qui": "5", "sex": "6", "s[áa]b": "7"}


def horario_to_sigaa(horario_raw: str) -> str:
    if not horario_raw:
        return ""
    slots: list[tuple[str, str, str]] = []
    for part in horario_raw.split("/"):
        m = re.match(
            r"(seg|ter|qua|qui|sex|s[áa]b)\.\s*(\d{2}:\d{2})-(\d{2}:\d{2})",
            _normalize(part.strip()),
        )
        if not m:
            continue
        day, start, end = m.groups()
        day_code = next((v for k, v in _DAY_MAP.items() if re.fullmatch(k, day)), "")
        if not day_code:
            continue
        t_start = datetime.strptime(start, "%H:%M").time()
        t_end = datetime.strptime(end, "%H:%M").time()
        for (period, hour_num), slot_time in SLOT_TIMES.items():
            if t_start <= slot_time <= t_end:
                slots.append((day_code, period, str(hour_num)))
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for day, period, hour in slots:
        grouped[(day, period)].add(hour)
    return " ".join(
        sorted(
            f"{day}{period}{''.join(sorted(hours, key=int))}"
            for (day, period), hours in grouped.items()
        )
    )


def process_row(row: list[str]) -> list[str]:
    while len(row) < 6:
        row.append("")

    six_col_disciplina = row[3].strip()
    five_col_disciplina = row[2].strip()

    if re.search(r"[A-Z]{2,}\d{3,}", six_col_disciplina):
        org, _periodo, turma, disciplina_full, docente, horario = row[:6]
    elif re.search(r"[A-Z]{2,}\d{3,}", five_col_disciplina):
        org, turma, disciplina_full, docente, horario = row[:5]
    else:
        return ["", "", "", "", "", "", ""]

    codigo, disciplina = split_codigo_disciplina(disciplina_full)
    docente = re.sub(r"\s+", " ", docente).strip()
    horario_raw, sala = split_horario_sala(horario)
    return [org, turma, codigo, disciplina, docente, horario_to_sigaa(horario_raw), sala]


def format_data(merged_rows: list[list[str]]) -> list[Course]:
    seen: set[tuple[str, str, str]] = set()
    courses: list[Course] = []
    for row in merged_rows[1:]:
        if not row or row[0].startswith("Período:") or row[0].startswith("Órgão ofertante"):
            continue
        orgao, turma, codigo, name, docente, horario, sala = process_row(row)
        if not codigo or not name:
            continue
        key = (codigo, turma, orgao)
        if key in seen:
            continue
        seen.add(key)
        courses.append(
            Course(
                orgao=orgao,
                turma=turma,
                codigo=codigo,
                name=name,
                docente=docente,
                horario=horario,
                sala=sala,
            )
        )
    return courses
