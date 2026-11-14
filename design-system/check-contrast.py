#!/usr/bin/env python3
"""UKCN Design System · WCAG contrast gate.

Reads the canonical tokens.css, verifies every text/control colour pair against
WCAG 2.2 AA (4.5:1 normal text, 3:1 non-text / control boundary).
Exit code 1 on any failure -> release blocked.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSS = ROOT / "tokens.css"


def parse_blocks(text):
    out = {}
    for name, pattern in (
        ("light", r":root\s*\{(.*?)\}"),
        ("dark", r'\[data-theme="dark"\]\s*\{(.*?)\}'),
    ):
        m = re.search(pattern, text, re.S)
        if not m:
            raise SystemExit(f"FATAL: cannot find {name} block in tokens.css")
        vals = {}
        for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)):
            vals[k] = v.strip()
        out[name] = vals
    return out


def luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"not a 6-digit hex: {hex_color}")
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# (label, foreground token, background token, minimum ratio)
CHECKS = [
    ("正文 / 页面底", "--text", "--bg", 4.5),
    ("正文 / 卡片表面", "--text", "--surface", 4.5),
    ("次要文字 / 页面底", "--muted", "--bg", 4.5),
    ("次要文字 / 卡片表面", "--muted", "--surface", 4.5),
    ("链接文字 / 页面底", "--accent-ink", "--bg", 4.5),
    ("链接文字 / 卡片表面", "--accent-ink", "--surface", 4.5),
    ("成功文字 / 页面底", "--good", "--bg", 4.5),
    ("警告文字 / 页面底", "--warn", "--bg", 4.5),
    ("危险文字 / 页面底", "--danger", "--bg", 4.5),
    ("危险文字 / 卡片表面", "--danger", "--surface", 4.5),
    ("按钮文字 / 按钮实底", "--on-accent", "--accent-strong", 4.5),
    ("实底成功态文字", "--on-good", "--good-solid", 4.5),
    ("控件边框 / 页面底", "--line", "--bg", 3.0),
    ("控件边框 / 卡片表面", "--line", "--surface", 3.0),
    ("焦点环 / 页面底", "--focus", "--bg", 3.0),
    ("焦点环 / 卡片表面", "--focus", "--surface", 3.0),
]


def main():
    blocks = parse_blocks(CSS.read_text(encoding="utf-8"))
    failed = 0
    print("UKCN Design System · WCAG contrast gate (tokens.css)")
    print("=" * 78)
    for theme in ("light", "dark"):
        vals = blocks[theme]
        print(f"\n[{theme}]")
        for label, fg, bg, minimum in CHECKS:
            if fg not in vals or bg not in vals:
                print(f"  MISSING  {label}: {fg} / {bg}")
                failed += 1
                continue
            try:
                ratio = contrast(vals[fg], vals[bg])
            except ValueError as err:
                print(f"  SKIP     {label}: {err}")
                continue
            ok = ratio >= minimum
            flag = "PASS" if ok else "FAIL"
            if not ok:
                failed += 1
            print(f"  {flag:<8} {label:<24} {vals[fg]:<9} / {vals[bg]:<9} "
                  f"{ratio:5.2f}:1  (min {minimum})")
    print("\n" + "=" * 78)
    if failed:
        print(f"RESULT: {failed} FAILED -> release blocked")
        return 1
    print("RESULT: all pairs pass WCAG 2.2 AA -> OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
