import argparse
import sys

from . import downloader
from .display import print_table, print_schedule
from .models import Course, DAY_CODES, PERIOD_NAMES, SLOT_TIMES, Schedule
from .scheduler import CourseScheduler


def build_scheduler(courses_file: str, schedule_file: str) -> CourseScheduler:
    try:
        return CourseScheduler(courses_file, schedule_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Erro: {e}")
        sys.exit(1)


def pick(
    courses: list[Course], schedule: Schedule, title: str = "Múltiplos resultados"
) -> Course | None:
    print_table(courses, schedule, title)
    print()
    try:
        raw = input(f"Selecione [1-{len(courses)}] ou Enter para cancelar: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(courses):
        return courses[int(raw) - 1]
    print("Seleção inválida.")
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Planejador de Matrícula CIn")
    sub = parser.add_subparsers(dest="command", required=True)

    def courses_arg(p: argparse.ArgumentParser):
        p.add_argument(
            "--courses",
            "-c",
            default="disciplinas.jsonl",
            help="Arquivo de disciplinas (.jsonl)",
        )

    def schedule_arg(p: argparse.ArgumentParser):
        p.add_argument("--schedule", "-s", default="schedule.json")

    # download
    dl = sub.add_parser("download")
    dl.add_argument("url")
    dl.add_argument("--output", "-o", default="disciplinas.jsonl")

    # list
    p = sub.add_parser("list")
    courses_arg(p)
    schedule_arg(p)

    # search
    search = sub.add_parser("search")
    courses_arg(search)
    schedule_arg(search)
    ss = search.add_subparsers(dest="search_type", required=True)
    ss.add_parser("code").add_argument("code")
    ss.add_parser("name").add_argument("name", nargs="+")
    ss.add_parser("time").add_argument("time_code")

    # add
    add = sub.add_parser("add")
    courses_arg(add)
    schedule_arg(add)
    as_ = add.add_subparsers(dest="add_type", required=True)
    as_.add_parser("code").add_argument("code")
    as_.add_parser("name").add_argument("name", nargs="+")

    # remove
    remove = sub.add_parser("remove")
    courses_arg(remove)
    schedule_arg(remove)
    remove.add_subparsers(dest="remove_type", required=True).add_parser("code").add_argument("code")

    # schedule
    p = sub.add_parser("schedule")
    courses_arg(p)
    schedule_arg(p)

    args = parser.parse_args(argv)

    if args.command == "download":
        try:
            total = downloader.download_to_jsonl(args.url, args.output)
            print(f"{total} disciplinas salvas em {args.output}")
        except Exception as e:
            print(f"Erro: {e}")
            sys.exit(1)
        return

    s = build_scheduler(args.courses, args.schedule)

    if args.command == "list":
        print_table(s.all_courses(), s.schedule, "Todas as disciplinas")

    elif args.command == "search":
        if args.search_type == "code":
            print_table(s.find_by_code(args.code), s.schedule, f"Código {args.code}")
        elif args.search_type == "name":
            name = " ".join(args.name)
            print_table(s.find_by_name(name), s.schedule, f"Nome similar a '{name}'")
        elif args.search_type == "time":
            tc = args.time_code.upper()
            courses, err = s.find_by_time_code(tc)
            if err:
                print(f"Erro: {err}")
                return
            day = DAY_CODES.get(tc[0], "?")
            period = PERIOD_NAMES.get(tc[1], "?").lower()
            hours = ", ".join(SLOT_TIMES[(tc[1], int(h))].strftime("%H:%M") for h in tc[2:])
            print_table(courses, s.schedule, f"{day} pela {period} nos horários: {hours}")

    elif args.command == "add":
        courses = (
            s.find_by_code(args.code)
            if args.add_type == "code"
            else s.find_by_name(" ".join(args.name))
        )
        if not courses:
            print("Nenhuma disciplina encontrada.")
        elif len(courses) == 1:
            s.add_course(courses[0])
        else:
            c = pick(courses, s.schedule)
            if c:
                s.add_course(c)

    elif args.command == "remove":
        courses = [c for c in s.find_by_code(args.code) if s.is_selected(c)]
        if not courses:
            print(f"Nenhuma disciplina selecionada com código {args.code}")
        elif len(courses) == 1:
            s.remove_course(courses[0])
        else:
            c = pick(courses, s.schedule)
            if c:
                s.remove_course(c)

    elif args.command == "schedule":
        selected = s.selected_courses()
        if selected:
            print_table(selected, s.schedule, "Disciplinas selecionadas")
            print()
        print_schedule(s.schedule)


if __name__ == "__main__":
    main()
