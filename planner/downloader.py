import csv
import io
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from . import formatter
from .models import Course


_PUB_RE = re.compile(r"/d/e/([\w-]+)/pubhtml")
_DOC_RE = re.compile(r"/spreadsheets/d/([\w-]+)")
_ITEMS_PUSH_GID_RE = re.compile(r'items.push\(\{name:\s*"[^"]+",\s*pageUrl:\s*".*?gid=(\d+)"')


def _get_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content.decode("utf-8-sig", errors="strict")


def _extract_gid(url: str) -> str | None:
    parsed = urlparse(url)
    query_gid = parse_qs(parsed.query).get("gid", [None])[0]
    if query_gid:
        return query_gid
    if "gid=" in parsed.fragment:
        frag_qs = parse_qs(parsed.fragment)
        return frag_qs.get("gid", [None])[0]
    return None


def _unique(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _extract_htmlview_gids(html: str) -> list[str]:
    return _unique(_ITEMS_PUSH_GID_RE.findall(html))


def _resolve_doc_and_gids(url: str) -> tuple[str, list[str], bool]:
    pub_match = _PUB_RE.search(url)
    if pub_match:
        doc_id = pub_match.group(1)
        html = _get_text(url)
        gids = _extract_htmlview_gids(html)
        if not gids:
            raise RuntimeError("No sheets found in provided URL")
        return doc_id, gids, True

    doc_match = _DOC_RE.search(url)
    if not doc_match:
        raise ValueError("URL does not appear to be a Google Sheets link")

    doc_id = doc_match.group(1)
    url_gid = _extract_gid(url)

    htmlview_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/htmlview"
    gids = _extract_htmlview_gids(_get_text(htmlview_url))
    if url_gid and url_gid not in gids:
        gids.insert(0, url_gid)
    if not gids:
        if url_gid:
            gids = [url_gid]
        else:
            raise RuntimeError("No sheets found in provided URL")

    return doc_id, gids, False


def download_and_merge(url: str) -> list[list[str]]:
    doc_id, gids, is_published = _resolve_doc_and_gids(url)

    merged: list[list[str]] = []
    header_written = False
    for gid in gids:
        if is_published:
            csv_url = (
                f"https://docs.google.com/spreadsheets/d/e/{doc_id}/pub"
                f"?gid={gid}&single=true&output=csv"
            )
        else:
            csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
        rows = list(csv.reader(io.StringIO(_get_text(csv_url))))
        if not rows:
            continue
        if not header_written:
            merged.append(rows[0])
            header_written = True
        merged.extend(rows[1:])
    if not merged:
        raise RuntimeError("No data found for the provided URL/gid")
    return merged


def download_courses(url: str) -> list[Course]:
    doc_id, gids, is_published = _resolve_doc_and_gids(url)

    courses: list[Course] = []
    seen: set[tuple[str, str, str]] = set()

    for gid in gids:
        if is_published:
            csv_url = (
                f"https://docs.google.com/spreadsheets/d/e/{doc_id}/pub"
                f"?gid={gid}&single=true&output=csv"
            )
        else:
            csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"

        rows = list(csv.reader(io.StringIO(_get_text(csv_url))))
        if not rows:
            continue

        for course in formatter.format_data(rows):
            key = course.key()
            if key in seen:
                continue
            seen.add(key)
            courses.append(course)

    if not courses:
        raise RuntimeError("No disciplines parsed from the provided URL")

    return courses


def write_courses_jsonl(courses: list[Course], output_file: str) -> int:
    path = Path(output_file)
    with path.open("w", encoding="utf-8") as f:
        for course in courses:
            f.write(json.dumps(course.to_dict(), ensure_ascii=False) + "\n")
    return len(courses)


def download_to_jsonl(url: str, output_file: str = "disciplinas.jsonl") -> int:
    courses = download_courses(url)
    return write_courses_jsonl(courses, output_file)
