# -*- coding: utf-8 -*-
"""Генератор учётных записей студентов МЭШ Колледж (локальный вход).
Читает data/students.tsv (ФИО<TAB>группа<TAB>форма) и выдаёт логин/пароль.
Логин: латиница (фамилия) + номер в общем списке.
Пароль: детерминированный SHA256(ФИО+группа), 10 символов, буквы+цифры.
"""
import hashlib
import os
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "students.tsv"
OUT_FILE = Path(os.path.expanduser("~")) / "OneDrive" / "Рабочий стол" / "ucetki_studentov.txt"

LATIN = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z",
         "и":"i","й":"i","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r",
         "с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch",
         "ъ":"","ы":"y","ь":"","э":"e","ю":"iu","я":"ia"}

def translit(word: str) -> str:
    out = []
    for ch in word.lower():
        out.append(LATIN.get(ch, ""))
    return "".join(out)

def gen_login(full_name: str, idx: int, used: set) -> str:
    parts = full_name.split()
    surname = translit(parts[0]) if parts else "st"
    base = surname[:16] or "st"
    login = f"{base}{idx:03d}"
    while login in used:
        login = f"{base}{idx:03d}x"
    used.add(login)
    return login

def gen_pass(full_name: str, group: str) -> str:
    h = hashlib.sha256(f"{full_name}|{group}|mesh-college-2026".encode("utf-8")).digest()
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    pwd = "".join(alphabet[b % len(alphabet)] for b in h[:10])
    return pwd

def parse_line(line: str):
    """Формат строки: №<any>ФИО<TAB>Группа<TAB>Форма"""
    return line

def main():
    rows = []
    used = set()
    with open(DATA_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if "\t" not in line:
                continue  # пропускаем заголовки без табов
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            fio = parts[0].strip()
            group = parts[1].strip() if len(parts) > 1 else ""
            forma = parts[2].strip() if len(parts) > 2 else ""
            if not fio or fio[0].isdigit():
                fio = re.sub(r"^\d+\s*", "", fio).strip()
            if not fio:
                continue
            rows.append((fio, group, forma))

    lines_out = []
    lines_out.append("УЧЁТНЫЕ ЗАПИСИ СТУДЕНТОВ — МЭШ КОЛЛЕДЖ (локальный вход)")
    lines_out.append("Формат: № | ФИО | группа | форма | логин | пароль")
    lines_out.append("=" * 90)
    for i, (fio, group, forma) in enumerate(rows, 1):
        login = gen_login(fio, i, used)
        pwd = gen_pass(fio, group)
        lines_out.append(f"{i} | {fio} | {group} | {forma} | {login} | {pwd}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("\n".join(lines_out), encoding="utf-8")
    print(f"Записано учёток: {len(rows)}")
    print(f"Файл: {OUT_FILE}")

if __name__ == "__main__":
    main()
