"""Минификация style.css -> style.min.css без внешних зависимостей."""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent


def minify_css(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"\s+", " ", source)
    source = re.sub(r"\s*([{}:;,>])\s*", r"\1", source)
    source = re.sub(r";}", "}", source)
    return source.strip()


def main() -> int:
    src = root / "css" / "style.css"
    dst = root / "css" / "style.min.css"
    if not src.exists():
        print("style.css не найден")
        return 1
    out = minify_css(src.read_text(encoding="utf-8"))
    dst.write_text(out, encoding="utf-8")
    print(f"minified: {len(out)} bytes -> {dst.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())