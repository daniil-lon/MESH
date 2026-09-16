# -*- coding: utf-8 -*-
"""Парсинг списка кураторов в JSON: группа -> {fio, phone, center}."""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
RAW = DATA / "curators_raw.txt"
OUT = DATA / "curators.json"

GROUP_RE = re.compile(r"^(\d[\w\-]+(?:-\d+)*)")
PHONE_RE = re.compile(r"(?:\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$")


def clean_phone(raw: str) -> str:
    digits = re.sub(r"[\s\-()]", "", raw)
    if digits.startswith("8") and len(digits) == 11:
        return "+7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return "+7" + digits[1:]
    return "+7" + digits[-10:] if len(digits) >= 10 else digits


def main():
    curators = {}
    center = ""
    for line in RAW.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") or "::" in line or "Ф.И.О." in line or "Номер телефона" in line:
            continue
        if not GROUP_RE.match(line) and not any(c.isdigit() for c in line):
            center = line.rstrip(":").strip()
            continue

        m = GROUP_RE.match(line)
        if not m:
            continue
        group = m.group(1)
        rest = line[m.end():].strip()
        rest = re.sub(r"^\(?вб\)?\s*", "", rest).strip()

        toks = rest.split()
        phone = ""
        fio_toks = []
        for t in reversed(toks):
            if t.replace("(", "").replace(")", "").replace("-", "").replace(" ", "").isdigit():
                if not phone:
                    phone = t
                else:
                    phone = t + phone
            elif t.replace("-", "").isdigit() and len(t.replace("-", "")) <= 3:
                if not phone:
                    phone = t
                else:
                    phone = t + phone
            else:
                break
        fio_toks = toks[: len(toks) - len(phone.split())] if phone else toks
        if not phone:
            all_digits = [t for t in toks if t.replace("-", "").isdigit()]
            if all_digits:
                phone = all_digits[-1]
                fio_toks = [t for t in toks if t not in all_digits]

        curators[group] = {
            "fio": " ".join(fio_toks).strip(),
            "phone": clean_phone(phone) if phone else "",
            "center": center,
        }

    OUT.write_text(json.dumps(curators, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Всего кураторов: {len(curators)}")


if __name__ == "__main__":
    main()