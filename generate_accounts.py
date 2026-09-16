# -*- coding: utf-8 -*-
"""Генератор учётных записей студентов МЭШ Колледж (локальный вход).

Читает все файлы data/sp_*.txt (ФИО<TAB>Группа<TAB>Форма), генерирует логин
(фамилия латиницей + следующий номер) и детерминированный пароль per-student.
Вывод: ucetki_studentov.txt на Рабочий стол + backend/data/students.json.
"""
import hashlib
import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "OneDrive" / "Рабочий стол"
TXT_OUT = DESKTOP / "ucetki_studentov.txt"
JSON_OUT = BASE_DIR / "backend" / "data" / "students.json"

LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}


def translit(word: str) -> str:
    return "".join(LAT.get(ch, ch if ch.isascii() else "") for ch in word.lower())


def gen_login(full_name: str, idx: int, used: set) -> str:
    parts = full_name.split()
    surname = parts[0] if parts else "st"
    base = translit(surname) or "st"
    login = f"{base}{idx:04d}"
    while login in used:
        login = f"{base}{idx:04d}x"
    used.add(login)
    return login


def gen_pass(full_name: str, group: str) -> str:
    h = hashlib.sha256(f"{full_name}|{group}|mesh-college-2026".encode("utf-8")).digest()
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(alphabet[b % len(alphabet)] for b in h[:10])


def load_students():
    students = []
    for f in sorted(DATA_DIR.glob("sp_*.txt")):
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                fio = re.sub(r"^\d+\s*", "", parts[1]).strip()
                group = parts[-2].strip()
                forma = parts[-1].strip()
                if not fio or not re.search(r"[А-Яа-яЁё]", fio):
                    continue
                students.append({"fio": fio, "group": group, "forma": forma})
    return students


def main():
    students = load_students()
    if not students:
        print("!! Нет студентов в data/sp_*.txt")
        return

    used = set()
    accounts = []
    for i, s in enumerate(students, 1):
        login = gen_login(s["fio"], i, used)
        pwd = gen_pass(s["fio"], s["group"])
        accounts.append({**s, "login": login, "password": pwd})

    lines = ["№\tФИО\tГруппа\tФорма\tЛогин\tПароль"]
    for i, s in enumerate(accounts, 1):
        lines.append(f"{i}\t{s['fio']}\t{s['group']}\t{s['forma']}\t{s['login']}\t{s['password']}")

    TXT_OUT.parent.mkdir(parents=True, exist_ok=True)
    TXT_OUT.write_text("\n".join(lines), encoding="utf-8")
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(accounts, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Всего учёток: {len(accounts)}")
    print(f"TXT : {TXT_OUT}")
    print(f"JSON: {JSON_OUT}")


if __name__ == "__main__":
    main()