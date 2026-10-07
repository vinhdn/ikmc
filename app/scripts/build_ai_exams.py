#!/usr/bin/env python3
"""Build the "AI generate" pilot set: 5 exams x 24 questions (IKMC Pre-Ecolier, lớp 1-2).

Each question is a variant of a question type found in the official 2014-2023 bank.
Answers are always computed by code from the same parameters that draw the figure,
and the build aborts if any option set is ambiguous (duplicate options, answer not
unique, puzzle with more than one solution).

Output:
  server/data/ai_exams.seed.json
  public/question-images/ai/e{N}/qNN.svg

Run: python3 scripts/build_ai_exams.py
"""
from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG_ROOT = ROOT / "public/question-images/ai"
OUT = ROOT / "server/data/ai_exams.seed.json"

LETTERS = "ABCDE"
DAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PALETTE = ["#e63946", "#3a86ff", "#2a9d8f", "#ffbe0b", "#fb8500", "#8338ec", "#ff70a6"]
INK = "#1f2937"
KIND_VI = {
    "circle": "hình tròn", "triangle": "hình tam giác", "square": "hình vuông",
    "star": "ngôi sao", "heart": "hình trái tim",
}
KIND_EN = {"circle": "circles", "triangle": "triangles", "square": "squares", "star": "stars", "heart": "hearts"}
KIND_NAME_VI = {
    "circle": "Hình tròn", "triangle": "Hình tam giác", "square": "Hình vuông",
    "star": "Ngôi sao", "heart": "Trái tim",
}


class BuildError(RuntimeError):
    pass


# ---------------------------------------------------------------- SVG helpers

def svg_doc(w: int, h: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'font-family="Arial, Helvetica, sans-serif"><rect width="{w}" height="{h}" fill="#ffffff"/>{body}</svg>'
    )


def text(x, y, s, size=18, anchor="middle", weight="bold", fill=INK):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{fill}" dominant-baseline="middle">{s}</text>'
    )


def poly(points, fill, stroke=INK, width=2):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"/>'


def shape(kind, cx, cy, r, fill, rot=0):
    if kind == "circle":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{INK}" stroke-width="2"/>'
    if kind == "square":
        s = r * 1.55
        return (
            f'<rect x="{cx - s / 2:.1f}" y="{cy - s / 2:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{fill}" '
            f'stroke="{INK}" stroke-width="2" transform="rotate({rot} {cx:.1f} {cy:.1f})"/>'
        )
    if kind == "triangle":
        pts = []
        for k in range(3):
            a = math.radians(rot - 90 + 120 * k)
            pts.append((cx + r * 1.1 * math.cos(a), cy + r * 1.1 * math.sin(a) + r * 0.15))
        return poly(pts, fill)
    if kind == "star":
        pts = []
        for k in range(10):
            rr = r * 1.15 if k % 2 == 0 else r * 0.48
            a = math.radians(rot - 90 + 36 * k)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        return poly(pts, fill)
    if kind == "heart":
        s = r
        d = (
            f"M {cx:.1f},{cy + 0.85 * s:.1f} "
            f"C {cx - 1.25 * s:.1f},{cy:.1f} {cx - 0.65 * s:.1f},{cy - 0.95 * s:.1f} {cx:.1f},{cy - 0.35 * s:.1f} "
            f"C {cx + 0.65 * s:.1f},{cy - 0.95 * s:.1f} {cx + 1.25 * s:.1f},{cy:.1f} {cx:.1f},{cy + 0.85 * s:.1f} Z"
        )
        return f'<path d="{d}" fill="{fill}" stroke="{INK}" stroke-width="2"/>'
    raise BuildError(f"unknown shape {kind}")


def label(x, y, letter):
    return text(x, y, f"({letter})", size=18)


def line(x1, y1, x2, y2, width=2, color=INK, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="round"{d}/>'
    )


def mini_shapes(kinds, x0, y0, w, h, rng, cols=3, r=11):
    """Lay out a list of shape kinds inside a box, in a jittered grid."""
    rows = math.ceil(len(kinds) / cols) or 1
    out = []
    order = list(kinds)
    for i, kind in enumerate(order):
        cx = x0 + (i % cols + 0.5) * w / cols + rng.uniform(-3, 3)
        cy = y0 + (i // cols + 0.5) * h / rows + rng.uniform(-3, 3)
        out.append(shape(kind, cx, cy, r, rng.choice(PALETTE), rot=rng.choice([0, 0, 180, 15, -15])))
    return "".join(out)


# ---------------------------------------------------------- option helpers

def numeric(ans, target, mistakes=(), lo=1, step=1, fmt=str):
    pool = []
    for m in mistakes:
        if m != ans and m >= lo and m not in pool:
            pool.append(m)
    d = 1
    while d < 80:
        for c in (ans - d * step, ans + d * step):
            if c >= lo and c != ans and c not in pool:
                pool.append(c)
        d += 1
    below = [c for c in pool if c < ans]
    above = [c for c in pool if c > ans]
    t = max(min(target, len(below)), 4 - len(above))
    chosen = below[:t] + above[: 4 - t]
    values = sorted(chosen + [ans])
    return [fmt(v) for v in values], values.index(ans)


def place(answer_text, others, target):
    others = [o for o in others if o != answer_text]
    seen = []
    for o in others:
        if o not in seen:
            seen.append(o)
    if len(seen) < 4:
        raise BuildError(f"not enough distractors for {answer_text}: {others}")
    opts = seen[:4]
    opts.insert(target, answer_text)
    return opts, target


def fmt_clock(minutes):
    minutes %= 24 * 60
    h = (minutes // 60) % 12
    h = 12 if h == 0 else h
    m = minutes % 60
    return f"{h} giờ" if m == 0 else f"{h} giờ {m} phút"


def fmt_clock_en(minutes):
    minutes %= 24 * 60
    h = (minutes // 60) % 12
    return f"{12 if h == 0 else h}:{minutes % 60:02d}"


def fmt_dur(minutes):
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} giờ {m} phút"
    if h:
        return f"{h} giờ"
    return f"{m} phút"


def fmt_dur_en(minutes):
    h, m = divmod(minutes, 60)
    parts = []
    if h:
        parts.append(f"{h} hour" + ("s" if h > 1 else ""))
    if m:
        parts.append(f"{m} minutes")
    return " ".join(parts)


def ordinal_en(n):
    return f"{n}" + ("st" if n % 10 == 1 and n != 11 else "nd" if n % 10 == 2 and n != 12 else "rd" if n % 10 == 3 and n != 13 else "th")


def join_vi(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " và " + items[-1]


def make(topic, vi, en, options, answer, expl, svg=None):
    return {"topic": topic, "vi": vi, "en": en, "options": options, "answer": answer, "expl": expl, "svg": svg}


# =========================================================== Section A (3 đ)

def a_count_shapes(p, t):
    rng = random.Random(p["seed"])
    items = [k for k, n in p["counts"].items() for _ in range(n)]
    rng.shuffle(items)
    cols = 8
    rows = math.ceil(len(items) / cols)
    body = []
    per_row = [0] * rows
    for i, kind in enumerate(items):
        r_i = i // cols
        if kind == p["kind"]:
            per_row[r_i] += 1
        cx = 45 + (i % cols) * 72 + rng.uniform(-8, 8)
        cy = 50 + r_i * 82 + rng.uniform(-8, 8)
        size = rng.uniform(17, 25)
        body.append(shape(kind, cx, cy, size, rng.choice(PALETTE), rot=rng.choice([0, 180, 25, -30, 90])))
    ans = p["counts"][p["kind"]]
    others = [v for k, v in p["counts"].items() if k != p["kind"]]
    opts, idx = numeric(ans, t, mistakes=[ans - 1, ans + 1, *others, len(items)])
    kv = KIND_VI[p["kind"]]
    row_txt = ", ".join(f"hàng {i + 1} có {c}" for i, c in enumerate(per_row))
    expl = [
        f"Đếm {kv} theo từng hàng để không bỏ sót: {row_txt}.",
        f"Cộng lại: {' + '.join(str(c) for c in per_row)} = {ans}.",
        f"Mẹo: {kv} dù bị xoay nghiêng hay lộn ngược vẫn là {kv}.",
    ]
    return make(
        "spatial", f"Trong hình có bao nhiêu {kv}?", f"How many {KIND_EN[p['kind']]} are in the picture?",
        opts, idx, expl, svg_doc(600, rows * 82 + 20, "".join(body)),
    )


DOT_POS = {
    1: [(-15, 4)], 2: [(-17, 0), (17, 0)], 3: [(-17, -6), (17, -6), (-14, 18)],
    4: [(-17, -6), (17, -6), (-15, 16), (15, 16)],
    5: [(-17, -8), (17, -8), (-24, 9), (24, 9), (-12, 23)],
    6: [(-17, -8), (17, -8), (-24, 9), (24, 9), (-13, 23), (13, 23)],
}


def ladybug(cx, cy, dots):
    out = [
        f'<ellipse cx="{cx}" cy="{cy}" rx="38" ry="32" fill="#e63946" stroke="{INK}" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy - 30}" r="14" fill="{INK}"/>',
        line(cx, cy - 18, cx, cy + 32, width=2),
    ]
    for dx, dy in DOT_POS[dots]:
        out.append(f'<circle cx="{cx + dx}" cy="{cy + dy}" r="5" fill="{INK}"/>')
    return "".join(out)


def a_dots(p, t):
    dots = p["dots"]
    n = len(dots)
    gap = 600 / n
    body = "".join(ladybug(gap * (i + 0.5), 75, d) for i, d in enumerate(dots))
    ans = sum(dots)
    opts, idx = numeric(ans, t, mistakes=[ans - 1, ans + 1, ans - dots[-1], ans + 2])
    expl = [
        "Đếm số chấm trên từng chú bọ rùa: " + ", ".join(str(d) for d in dots) + ".",
        f"Cộng lại: {' + '.join(str(d) for d in dots)} = {ans}.",
        "Mẹo: ghép các số thành cặp tròn chục (ví dụ 4 + 6 = 10) để cộng nhanh và ít nhầm.",
    ]
    return make(
        "arithmetic",
        f"Có {n} chú bọ rùa đậu trên lá. Tổng cộng các chú bọ rùa có bao nhiêu chấm?",
        f"There are {n} ladybirds on a leaf. How many dots do they have altogether?",
        opts, idx, expl, svg_doc(600, 130, body),
    )


def a_ladybug_fly(p, t):
    dots = list(p["others"])
    dots.insert(t, p["flyer"])
    if dots.count(p["flyer"]) != 1:
        raise BuildError("ladybug_fly: flyer value must be unique")
    total = sum(dots)
    remain = total - p["flyer"]
    body = []
    for i, d in enumerate(dots):
        cx = 60 + i * 120
        body.append(ladybug(cx, 70, d))
        body.append(label(cx, 128, LETTERS[i]))
    opts = [f"Bọ rùa {LETTERS[i]}" for i in range(5)]
    expl = [
        "Tổng số chấm của cả 5 chú: " + " + ".join(str(d) for d in dots) + f" = {total}.",
        f"Muốn còn lại {remain} chấm thì chú bay đi phải có {total} − {remain} = {p['flyer']} chấm.",
        f"Chỉ có bọ rùa {LETTERS[t]} có {p['flyer']} chấm.",
    ]
    return make(
        "arithmetic",
        f"Bọ rùa nào phải bay đi để những chú còn lại có tổng cộng {remain} chấm?",
        f"Which ladybird must fly away so that the others have {remain} dots altogether?",
        opts, t, expl, svg_doc(600, 145, "".join(body)),
    )


def a_day(p, t):
    d = p["day"]
    mode = p["mode"]
    if mode == "yesterday->tomorrow":
        ans = (d + 2) % 7
        vi = f"Hôm qua là {DAYS[d]}. Hỏi ngày mai là thứ mấy?"
        en = f"Yesterday was {DAYS_EN[d]}. What day will it be tomorrow?"
        expl = [
            f"Hôm qua là {DAYS[d]} nên hôm nay là {DAYS[(d + 1) % 7]}.",
            f"Ngày mai là ngày sau hôm nay: {DAYS[ans]}.",
            "Mẹo: vẽ một hàng các ngày trong tuần rồi đánh dấu hôm qua – hôm nay – ngày mai.",
        ]
    elif mode == "daybefore->dayafter":
        ans = (d + 4) % 7
        vi = f"Hôm kia là {DAYS[d]}. Hỏi ngày kia là thứ mấy?"
        en = f"The day before yesterday was {DAYS_EN[d]}. What day will it be the day after tomorrow?"
        expl = [
            f"Hôm kia là 2 ngày trước hôm nay, nên hôm nay là {DAYS[(d + 2) % 7]}.",
            f"Ngày kia là 2 ngày sau hôm nay: {DAYS[ans]}.",
            "Mẹo: từ hôm kia đến ngày kia cách nhau 4 ngày.",
        ]
    else:  # tomorrow->yesterday
        ans = (d - 2) % 7
        vi = f"Ngày mai là {DAYS[d]}. Hỏi hôm qua là thứ mấy?"
        en = f"Tomorrow will be {DAYS_EN[d]}. What day was it yesterday?"
        expl = [
            f"Ngày mai là {DAYS[d]} nên hôm nay là {DAYS[(d - 1) % 7]}.",
            f"Hôm qua là ngày trước hôm nay: {DAYS[ans]}.",
        ]
    others = [DAYS[(ans + k) % 7] for k in (-1, 1, 2, -2, 3)]
    opts, idx = place(DAYS[ans], others, t)
    return make("measurement", vi, en, opts, idx, expl)


def a_queue(p, t):
    n, a, b, x, y = p["n"], p["a"], p["b"], p["x"], p["y"]
    pos_y = n - b + 1
    if pos_y <= a:
        raise BuildError("queue: Y must stand behind X")
    ans = pos_y - a - 1
    opts, idx = numeric(ans, t, mistakes=[ans + 1, ans + 2, ans - 1, pos_y - a + 1], lo=0)
    expl = [
        f"Hàng có {n} bạn. {y} đứng thứ {b} tính từ cuối, nên tính từ đầu hàng {y} đứng thứ {n} − {b} + 1 = {pos_y}.",
        f"{x} đứng thứ {a}. Các bạn đứng giữa ở các vị trí từ {a + 1} đến {pos_y - 1}.",
        f"Số bạn đứng giữa: {pos_y - 1} − {a} = {ans} bạn.",
        "Mẹo: vẽ một hàng chấm tròn và đánh số để dễ đếm.",
    ]
    return make(
        "logic",
        f"Có {n} bạn nhỏ xếp thành một hàng. {x} đứng thứ {a} tính từ đầu hàng, {y} đứng thứ {b} tính từ cuối hàng. "
        f"Có bao nhiêu bạn đứng giữa {x} và {y}?",
        f"{n} children stand in a line. {x} is {ordinal_en(a)} from the front and {y} is {ordinal_en(b)} from the back. "
        f"How many children stand between {x} and {y}?",
        opts, idx, expl,
    )


def a_cake(p, t):
    big, small = p["big"], p["small"]
    rng = random.Random(p["seed"])
    candles = ["big"] * big + ["small"] * small
    rng.shuffle(candles)
    body = [
        '<rect x="110" y="140" width="380" height="90" rx="14" fill="#ffb3c6" stroke="#1f2937" stroke-width="2"/>',
        '<rect x="110" y="140" width="380" height="24" rx="10" fill="#ffffff" stroke="#1f2937" stroke-width="2"/>',
        '<rect x="90" y="228" width="420" height="14" rx="6" fill="#d4a373" stroke="#1f2937" stroke-width="2"/>',
    ]
    gap = 360 / len(candles)
    for i, c in enumerate(candles):
        x = 120 + gap * (i + 0.5)
        if c == "big":
            body.append(f'<rect x="{x - 7:.1f}" y="70" width="14" height="72" fill="#e63946" stroke="{INK}" stroke-width="2"/>')
            body.append(f'<path d="M {x:.1f} 50 Q {x + 9:.1f} 62 {x:.1f} 70 Q {x - 9:.1f} 62 {x:.1f} 50 Z" fill="#ffbe0b"/>')
        else:
            body.append(f'<rect x="{x - 4:.1f}" y="112" width="8" height="30" fill="#3a86ff" stroke="{INK}" stroke-width="2"/>')
            body.append(f'<path d="M {x:.1f} 96 Q {x + 6:.1f} 105 {x:.1f} 112 Q {x - 6:.1f} 105 {x:.1f} 96 Z" fill="#ffbe0b"/>')
    ans = 10 * big + small
    opts, idx = numeric(ans, t, mistakes=[10 * small + big, ans + 10, ans - 10, ans + 1, ans - 1])
    who_vi, who_en = p["who"]
    expl = [
        f"Có {big} cây nến to (mỗi cây 10 tuổi) → {big} × 10 = {10 * big} tuổi.",
        f"Có {small} cây nến nhỏ (mỗi cây 1 tuổi) → {small} tuổi.",
        f"{who_vi.capitalize()} có {10 * big} + {small} = {ans} tuổi.",
        "Chú ý: đếm riêng nến to và nến nhỏ, đừng đảo hàng chục với hàng đơn vị.",
    ]
    return make(
        "measurement",
        f"Đây là bánh sinh nhật của {who_vi}. Mỗi cây nến to là 10 tuổi, mỗi cây nến nhỏ là 1 tuổi. {who_vi.capitalize()} bao nhiêu tuổi?",
        f"This is {who_en}'s birthday cake. A big candle stands for 10 years and a small one for 1 year. How old is {who_en}?",
        opts, idx, expl, svg_doc(600, 250, "".join(body)),
    )


def a_pattern(p, t):
    unit, shown, k = p["unit"], p["shown"], p["k"]
    L = len(unit)
    seq = [unit[i % L] for i in range(shown)]
    body = []
    step = 560 / (shown + 1)
    for i, kind in enumerate(seq):
        cx = 30 + step * (i + 0.5)
        body.append(shape(kind, cx, 55, 20, PALETTE[unit.index(kind) % len(PALETTE)]))
        body.append(text(cx, 100, str(i + 1), size=14, weight="normal"))
    body.append(text(30 + step * (shown + 0.5), 55, "...", size=26))
    ans_kind = unit[(k - 1) % L]
    q, r = divmod(k, L)
    names = [KIND_NAME_VI[x] for x in ["circle", "triangle", "square", "star", "heart"]]
    opts, idx = place(KIND_NAME_VI[ans_kind], names, t)
    group = ", ".join(KIND_VI[u] for u in unit)
    if r == 0:
        step_txt = f"{k} = {L} × {q}, nên hình thứ {k} là hình cuối cùng của một nhóm: {KIND_VI[ans_kind]}."
    else:
        step_txt = f"{k} = {L} × {q} + {r}, nên hình thứ {k} giống hình thứ {r} trong nhóm: {KIND_VI[ans_kind]}."
    expl = [
        f"Nhóm hình lặp lại gồm {L} hình: {group}.",
        step_txt,
        "Mẹo: tìm nhóm lặp lại trước, rồi chia vị trí cần tìm cho số hình trong nhóm.",
    ]
    return make(
        "logic",
        f"Bạn Na xếp các hình theo một quy luật lặp lại như hình vẽ. Hình thứ {k} là hình gì?",
        f"Na arranges shapes in a repeating pattern as shown. What is the {ordinal_en(k)} shape?",
        opts, idx, expl, svg_doc(600, 120, "".join(body)),
    )


def a_grid_missing(p, t):
    n, missing = p["n"], set(p["missing"])
    cell = 46
    x0 = (600 - n * cell) / 2
    body = []
    present_rows = []
    for r in range(n):
        cnt = 0
        for c in range(n):
            if (r, c) in missing:
                body.append(
                    f'<rect x="{x0 + c * cell + 3:.1f}" y="{18 + r * cell}" width="{cell - 6}" height="{cell - 6}" '
                    f'fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5 4"/>'
                )
                continue
            cnt += 1
            body.append(
                f'<rect x="{x0 + c * cell:.1f}" y="{15 + r * cell}" width="{cell}" height="{cell}" '
                f'fill="#bde0fe" stroke="{INK}" stroke-width="2"/>'
            )
        present_rows.append(cnt)
    ans = len(missing)
    total = n * n
    opts, idx = numeric(ans, t, mistakes=[ans - 1, ans + 1, ans + 2, total - ans])
    expl = [
        f"Hình vuông lớn có {n} hàng, mỗi hàng {n} ô, tất cả {n} × {n} = {total} ô.",
        "Đếm số ô còn lại theo từng hàng: " + " + ".join(str(c) for c in present_rows) + f" = {total - ans} ô.",
        f"Số ô bị mất: {total} − {total - ans} = {ans} ô.",
    ]
    return make(
        "spatial",
        f"Một hình vuông lớn được ghép từ {total} ô vuông nhỏ ({n} hàng, mỗi hàng {n} ô). Một số ô đã bị rơi mất, để lại các chỗ trống (ô viền nét đứt). Có bao nhiêu ô bị mất?",
        f"A big square was made of {total} small squares ({n} rows of {n}). Some squares fell out. How many squares are missing?",
        opts, idx, expl, svg_doc(600, n * cell + 30, "".join(body)),
    )


def a_equalize(p, t):
    x, y, a, b, item_vi, item_en = p["x"], p["y"], p["a"], p["b"], p["item_vi"], p["item_en"]
    if (y - x) % 2:
        raise BuildError("equalize needs even difference")
    ans = (y - x) // 2
    each = (x + y) // 2
    opts, idx = numeric(ans, t, mistakes=[y - x, ans + 1, ans - 1, each])
    expl = [
        f"Hai bạn có tất cả {x} + {y} = {x + y} {item_vi}.",
        f"Chia đều thì mỗi bạn có {x + y} : 2 = {each} {item_vi}.",
        f"{b} có {y}, cần đưa cho {a}: {y} − {each} = {ans} {item_vi}.",
        f"Chú ý: không phải {y} − {x} = {y - x}, vì khi {b} đưa đi thì {b} cũng bị bớt.",
    ]
    return make(
        "arithmetic",
        f"{a} có {x} {item_vi}, {b} có {y} {item_vi}. {b} cần cho {a} bao nhiêu {item_vi} để hai bạn có số {item_vi} bằng nhau?",
        f"{a} has {x} {item_en} and {b} has {y}. How many {item_en} must {b} give {a} so they have the same number?",
        opts, idx, expl,
    )


def a_midpoint(p, t):
    a, b = p["a"], p["b"]
    if (a + b) % 2:
        raise BuildError("midpoint must be whole")
    ans = (a + b) // 2
    half = (b - a) // 2
    opts, idx = numeric(ans, t, mistakes=[b - a, half, ans + 1, ans - 1, ans + 2])
    expl = [
        f"Khoảng cách từ {a} đến {b} là {b} − {a} = {b - a}.",
        f"Số chính giữa cách mỗi đầu một nửa khoảng đó: {b - a} : 2 = {half}.",
        f"Số cần tìm: {a} + {half} = {ans} (kiểm tra: {ans} + {half} = {b}).",
    ]
    return make(
        "arithmetic",
        f"Số nào nằm chính giữa hai số {a} và {b} trên tia số?",
        f"Which number is exactly halfway between {a} and {b}?",
        opts, idx, expl,
    )


def a_largest_below(p, t):
    n, exprs = p["n"], p["exprs"]
    vals = {e: eval(e.replace("−", "-")) for e in exprs}
    below = [e for e in exprs if vals[e] < n]
    best = max(vals[e] for e in below)
    winners = [e for e in below if vals[e] == best]
    if len(winners) != 1:
        raise BuildError("largest_below not unique")
    ans_e = winners[0]
    opts, idx = place(ans_e, [e for e in exprs if e != ans_e], t)
    calc = "; ".join(f"{e} = {vals[e]}" for e in opts)
    expl = [
        f"Tính từng phép: {calc}.",
        f"Loại các kết quả không nhỏ hơn {n}.",
        f"Trong các kết quả còn lại, lớn nhất là {best} (phép tính {ans_e}).",
    ]
    return make(
        "arithmetic",
        f"Phép tính nào cho kết quả lớn nhất nhưng vẫn nhỏ hơn {n}?",
        f"Which calculation gives the largest result that is still smaller than {n}?",
        opts, idx, expl,
    )


def clock_svg(minutes):
    cx, cy, R = 300, 120, 100
    out = [f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#fffbea" stroke="{INK}" stroke-width="4"/>']
    for k in range(60):
        a = math.radians(k * 6 - 90)
        r1 = R - (12 if k % 5 == 0 else 6)
        out.append(line(cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + (R - 2) * math.cos(a), cy + (R - 2) * math.sin(a),
                        width=3 if k % 5 == 0 else 1))
    for h in range(1, 13):
        a = math.radians(h * 30 - 90)
        out.append(text(cx + (R - 26) * math.cos(a), cy + (R - 26) * math.sin(a), str(h), size=18))
    h = (minutes // 60) % 12
    m = minutes % 60
    ah = math.radians((h + m / 60) * 30 - 90)
    am = math.radians(m * 6 - 90)
    out.append(line(cx, cy, cx + 44 * math.cos(ah), cy + 44 * math.sin(ah), width=7))
    out.append(line(cx, cy, cx + 64 * math.cos(am), cy + 64 * math.sin(am), width=4, color="#e63946"))
    out.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{INK}"/>')
    return svg_doc(600, 240, "".join(out))


def a_clock(p, t):
    start = p["h"] * 60 + p["m"]
    add = p["add"]
    ans = start + add
    opts, idx = numeric(ans, t, mistakes=[start, ans + 30, ans - 30, ans + 60, ans - 60], step=30, lo=0, fmt=fmt_clock)
    expl = [
        f"Kim ngắn chỉ giờ, kim dài (màu đỏ) chỉ phút: đồng hồ đang chỉ {fmt_clock(start)}.",
        f"Thêm {fmt_dur(add)}: {fmt_clock(start)} + {fmt_dur(add)} = {fmt_clock(ans)}.",
        "Mẹo: kim dài chỉ số 6 là 30 phút (rưỡi), chỉ số 12 là giờ đúng.",
    ]
    return make(
        "measurement",
        f"Đồng hồ chỉ giờ như hình. Sau {fmt_dur(add)} nữa thì đồng hồ chỉ mấy giờ?",
        f"The clock shows the time. What time will it be {fmt_dur_en(add)} later?",
        opts, idx, expl, clock_svg(start),
    )


def boxes_svg(contents, rng, title_letters=True):
    body = []
    for i, kinds in enumerate(contents):
        x = 10 + i * 118
        body.append(f'<rect x="{x}" y="10" width="106" height="120" rx="12" fill="#f8fafc" stroke="{INK}" stroke-width="2"/>')
        crowded = len(kinds) > 9
        body.append(mini_shapes(kinds, x + 4, 14, 98, 112, rng, cols=4 if crowded else 3, r=9 if crowded else 11))
        if title_letters:
            body.append(label(x + 53, 150, LETTERS[i]))
    return svg_doc(600, 165, "".join(body))


def a_most_shape(p, t):
    rng = random.Random(p["seed"])
    counts = list(p["others"])
    counts.insert(t, p["max"])
    if sorted(counts)[-2] >= p["max"]:
        raise BuildError("most_shape max not unique")
    fillers = [k for k in ["circle", "triangle", "square", "star", "heart"] if k != p["kind"]]
    contents = []
    for c in counts:
        extra = rng.randint(1, max(1, 9 - c))
        kinds = [p["kind"]] * c + [rng.choice(fillers) for _ in range(extra)]
        rng.shuffle(kinds)
        if kinds.count(p["kind"]) != c:
            raise BuildError("most_shape drawn count mismatch")
        contents.append(kinds)
    opts = [f"Hộp {LETTERS[i]}" for i in range(5)]
    kv = KIND_VI[p["kind"]]
    expl = [
        "Đếm " + kv + " trong từng hộp: " + ", ".join(f"hộp {LETTERS[i]} có {c}" for i, c in enumerate(counts)) + ".",
        f"Hộp {LETTERS[t]} có nhiều {kv} nhất ({p['max']}).",
        "Mẹo: chỉ đếm đúng loại hình được hỏi, bỏ qua các hình khác.",
    ]
    return make(
        "spatial", f"Hộp nào có nhiều {kv} nhất?", f"Which box has the most {KIND_EN[p['kind']]}?",
        opts, t, expl, boxes_svg(contents, rng),
    )


def a_attr(p, t):
    rng = random.Random(p["seed"])
    cards = list(p["others"])
    cards.insert(t, p["target"])
    ok = [i for i, card in enumerate(cards) if p["rule"](*card)]
    if ok != [t]:
        raise BuildError(f"attr rule not unique: {ok}")
    contents = []
    for c, tr, sq in cards:
        kinds = ["circle"] * c + ["triangle"] * tr + ["square"] * sq
        rng.shuffle(kinds)
        contents.append(kinds)
    opts = [f"{p['noun']} {LETTERS[i]}" for i in range(5)]
    checks = []
    for i, (c, tr, sq) in enumerate(cards):
        checks.append(f"{LETTERS[i]}: {c} tròn, {tr} tam giác, {sq} vuông")
    expl = [
        "Đếm từng loại hình: " + "; ".join(checks) + ".",
        p["why"],
        f"Chỉ có {p['noun'].lower()} {LETTERS[t]} đúng cả hai điều kiện.",
    ]
    return make("logic", p["vi"], p["en"], opts, t, expl, boxes_svg(contents, rng))


def a_stairs(p, t):
    S, a, b = p["S"], p["a"], p["b"]
    if S % (a + b):
        raise BuildError("stairs must meet exactly")
    turns = S // (a + b)
    ans = a * turns
    w = 520 / (S + 1)
    body = []
    for s in range(S + 1):
        x = 40 + s * w
        y = 210 - s * 15
        body.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{230 - y}" fill="#e9edc9" stroke="{INK}" stroke-width="1.5"/>')
        body.append(text(x + w / 2, y + 12, str(s), size=13))
    body.append(text(40 + w / 2, 182, "K", size=22, fill="#fb8500"))
    body.append(text(40 + S * w + w / 2, 210 - S * 15 - 22, "T", size=22, fill="#3a86ff"))
    rows = []
    for k in range(1, turns + 1):
        rows.append(f"lượt {k}: chuột túi ở bậc {a * k}, thỏ ở bậc {S - b * k}")
    opts, idx = numeric(ans, t, mistakes=[S // 2, ans + a, ans - b, S - ans], lo=0)
    expl = [
        f"Mỗi lượt hai bạn lại gần nhau thêm {a} + {b} = {a + b} bậc.",
        "Theo dõi từng lượt: " + "; ".join(rows) + ".",
        f"Sau {turns} lượt cả hai cùng ở bậc {ans}.",
    ]
    return make(
        "measurement",
        f"Cầu thang có các bậc được đánh số từ 0 đến {S}. Chuột túi (K) đứng ở bậc 0, thỏ (T) đứng ở bậc {S}. "
        f"Mỗi lượt, chuột túi đi lên {a} bậc và cùng lúc thỏ đi xuống {b} bậc. Hai bạn gặp nhau ở bậc nào?",
        f"Stairs are numbered 0 to {S}. The kangaroo (K) is on step 0 and the rabbit (T) on step {S}. "
        f"Each turn the kangaroo goes up {a} steps while the rabbit goes down {b}. On which step do they meet?",
        opts, idx, expl, svg_doc(600, 240, "".join(body)),
    )


def a_weight(p, t):
    total, mother, an_vi, an_en = p["total"], p["mother"], p["animal_vi"], p["animal_en"]
    ans = total - mother
    opts, idx = numeric(ans, t, mistakes=[total + mother, mother - ans, ans + 1, ans - 1, ans + 10],
                        fmt=lambda v: f"{v} kg")
    expl = [
        f"Cả hai cùng nặng {total} kg, riêng {an_vi} mẹ nặng {mother} kg.",
        f"{an_vi.capitalize()} con nặng: {total} − {mother} = {ans} kg.",
        f"Kiểm tra: {mother} + {ans} = {total} kg.",
    ]
    return make(
        "measurement",
        f"{an_vi.capitalize()} mẹ và {an_vi} con cùng nặng {total} kg. Riêng {an_vi} mẹ nặng {mother} kg. {an_vi.capitalize()} con nặng bao nhiêu ki-lô-gam?",
        f"A mother {an_en} and her baby weigh {total} kg together. The mother weighs {mother} kg. How much does the baby weigh?",
        opts, idx, expl,
    )


def a_ages(p, t):
    a, diff, name = p["a"], p["diff"], p["name"]
    ans = 2 * a + diff
    opts, idx = numeric(ans, t, mistakes=[a + diff, 2 * a, ans + diff, ans - 1, ans + 1])
    expl = [
        f"{name} {a} tuổi, anh trai hơn {diff} tuổi nên anh {a} + {diff} = {a + diff} tuổi.",
        f"Tổng số tuổi hai anh em: {a} + {a + diff} = {ans} tuổi.",
        f"Chú ý: {a + diff} là tuổi của anh, chưa phải tổng.",
    ]
    return make(
        "measurement",
        f"{name} năm nay {a} tuổi. Anh trai của {name} hơn {name} {diff} tuổi. Tổng số tuổi của hai anh em là bao nhiêu?",
        f"{name} is {a} years old. Her brother is {diff} years older. What is the sum of their ages?",
        opts, idx, expl,
    )


# =========================================================== Section B (4 đ)

def balance_svg(scales):
    """scales: list of (left_kinds, right_kinds_or_'?')."""
    body = []
    n = len(scales)
    width = 600 / n
    colors = {"circle": "#e63946", "square": "#3a86ff", "triangle": "#2a9d8f"}
    for i, (left, right) in enumerate(scales):
        cx = width * (i + 0.5)
        beam_y, pan_y, base_y = 70, 150, 215
        body.append(poly([(cx, beam_y), (cx - 20, base_y), (cx + 20, base_y)], "#adb5bd"))
        body.append(line(cx - 62, beam_y, cx + 62, beam_y, width=5))
        for side, items in ((-1, left), (1, right)):
            px = cx + side * 62
            body.append(line(px, beam_y, px - 26, pan_y, width=1.5))
            body.append(line(px, beam_y, px + 26, pan_y, width=1.5))
            body.append(line(px - 30, pan_y, px + 30, pan_y, width=4))
            if items == "?":
                body.append(text(px, pan_y - 20, "?", size=32, fill="#e63946"))
                continue
            for j, kind in enumerate(items):
                col, row = j % 3, j // 3
                per_row = min(3, len(items) - row * 3)
                ix = px + (col - (per_row - 1) / 2) * 19
                iy = pan_y - 11 - row * 20
                body.append(shape(kind, ix, iy, 8.5, colors[kind]))
        body.append(text(cx, 232, f"Cân {i + 1}", size=15, weight="normal"))
    return svg_doc(600, 245, "".join(body))


def b_balance(p, t):
    k1, k2, e = p["k1"], p["k2"], p["e"]
    ans = k1 * k2 + e
    scales = [(["square"], ["circle"] * k1), (["triangle"], ["square"] * k2 + ["circle"] * e), (["triangle"], "?")]
    extra_vi = f" và {e} hình tròn" if e else ""
    opts, idx = numeric(ans, t, mistakes=[k1 + k2 + e, k1 * k2, k2 + e, ans + 1, ans - 1])
    expl = [
        f"Cân 1: 1 hình vuông nặng bằng {k1} hình tròn.",
        f"Cân 2: 1 hình tam giác nặng bằng {k2} hình vuông{extra_vi}.",
        f"Đổi mỗi hình vuông thành {k1} hình tròn: {k2} hình vuông = {k2} × {k1} = {k1 * k2} hình tròn.",
        f"Vậy 1 hình tam giác nặng bằng {k1 * k2}" + (f" + {e} = {ans}" if e else "") + " hình tròn.",
        "Mẹo: thay dần các hình nặng hơn bằng các hình nhỏ nhất.",
    ]
    return make(
        "measurement",
        "Cân 1 và cân 2 đang thăng bằng. Cần đặt bao nhiêu hình tròn lên đĩa bên phải để cân 3 cũng thăng bằng?",
        "Scales 1 and 2 are balanced. How many circles must go on the right pan so that scale 3 balances too?",
        opts, idx, expl, balance_svg(scales),
    )


def equation_svg(lines_tokens):
    body = []
    colors = {"square": "#3a86ff", "triangle": "#2a9d8f", "circle": "#e63946", "star": "#ffbe0b", "heart": "#ff70a6"}
    for li, tokens in enumerate(lines_tokens):
        x = 150
        y = 40 + li * 62
        for tok in tokens:
            if tok in colors:
                body.append(shape(tok, x, y, 17, colors[tok]))
            else:
                body.append(text(x, y + 2, tok, size=28, fill="#e63946" if tok == "?" else INK))
            x += 50
    return svg_doc(600, 40 + 62 * len(lines_tokens) - 10, "".join(body))


def b_symbols(p, t):
    mode = p["mode"]
    if mode == "two":
        s1, n1, s2, n2, ask = p["s1"], p["n1"], p["s2"], p["n2"], p["ask"]
        v = {s1: p["v1"], s2: p["v2"]}
        lines = [
            sum(([s1, "+"] for _ in range(n1)), [])[:-1] + ["=", str(n1 * v[s1])],
            sum(([s2, "+"] for _ in range(n2)), [])[:-1] + ["=", str(n2 * v[s2])],
            sum(([s, "+"] for s in ask), [])[:-1] + ["=", "?"],
        ]
        ans = sum(v[s] for s in ask)
        expl = [
            f"{n1} {KIND_VI[s1]} bằng {n1 * v[s1]}, nên 1 {KIND_VI[s1]} = {n1 * v[s1]} : {n1} = {v[s1]}.",
            f"{n2} {KIND_VI[s2]} bằng {n2 * v[s2]}, nên 1 {KIND_VI[s2]} = {n2 * v[s2]} : {n2} = {v[s2]}.",
            "Thay vào dòng cuối: " + " + ".join(str(v[s]) for s in ask) + f" = {ans}.",
        ]
    else:  # chain: n1*s1 = A ; s1 + s2 = B ; ask
        s1, n1, s2, ask = p["s1"], p["n1"], p["s2"], p["ask"]
        v1, v2 = p["v1"], p["v2"]
        v = {s1: v1, s2: v2}
        lines = [
            sum(([s1, "+"] for _ in range(n1)), [])[:-1] + ["=", str(n1 * v1)],
            [s1, "+", s2, "=", str(v1 + v2)],
            sum(([s, "+"] for s in ask), [])[:-1] + ["=", "?"],
        ]
        ans = sum(v[s] for s in ask)
        expl = [
            f"Dòng 1: {n1} {KIND_VI[s1]} = {n1 * v1}, nên 1 {KIND_VI[s1]} = {v1}.",
            f"Dòng 2: {v1} + {KIND_VI[s2]} = {v1 + v2}, nên {KIND_VI[s2]} = {v1 + v2} − {v1} = {v2}.",
            "Dòng 3: " + " + ".join(str(v[s]) for s in ask) + f" = {ans}.",
        ]
    opts, idx = numeric(ans, t, mistakes=[ans + 1, ans - 1, ans + 2, ans - 2])
    return make(
        "logic",
        "Mỗi hình tượng trưng cho một số; các hình giống nhau là cùng một số. Số nào thay cho dấu “?”?",
        "Each shape stands for a number; equal shapes are equal numbers. Which number replaces the “?”?",
        opts, idx, expl, equation_svg(lines),
    )


def b_pizza(p, t):
    pizzas, slices, people, each = p["pizzas"], p["slices"], p["people"], p["each"]
    total = pizzas * slices
    ans = total - people * each
    if ans <= 0:
        raise BuildError("pizza leftover must be positive")
    opts, idx = numeric(ans, t, mistakes=[total - people, ans + each, ans - 1, ans + 1], lo=1)
    expl = [
        f"Số miếng bánh: {pizzas} × {slices} = {total} miếng.",
        f"{people} bạn, mỗi bạn ăn {each} miếng: {people} × {each} = {people * each} miếng.",
        f"Còn lại: {total} − {people * each} = {ans} miếng.",
    ]
    return make(
        "arithmetic",
        f"Mẹ nướng {pizzas} chiếc bánh pizza, mỗi chiếc cắt thành {slices} miếng bằng nhau. "
        f"Có {people} bạn nhỏ, mỗi bạn ăn {each} miếng. Hỏi còn lại bao nhiêu miếng bánh?",
        f"Mum bakes {pizzas} pizzas, each cut into {slices} equal slices. {people} children each eat {each} slices. How many slices are left?",
        opts, idx, expl,
    )


def b_digits(p, t):
    lo, hi, digits = p["lo"], p["hi"], p["digits"]
    nums = [n for n in range(lo, hi + 1) if set(str(n)) <= set(map(str, digits))]
    ans = len(nums)
    opts, idx = numeric(ans, t, mistakes=[ans - 1, ans + 1, ans + 2, len(digits) ** 2])
    dg = ", ".join(map(str, digits))
    expl = [
        f"Liệt kê các số từ {lo} đến {hi} chỉ dùng chữ số {dg}: " + ", ".join(map(str, nums)) + ".",
        f"Đếm được {ans} số.",
        "Mẹo: liệt kê theo hàng chục (chục 1, chục 2, ...) để không bỏ sót.",
    ]
    return make(
        "arithmetic",
        f"Có bao nhiêu số từ {lo} đến {hi} chỉ được viết bằng các chữ số {dg}? (Mỗi chữ số có thể dùng nhiều lần.)",
        f"How many numbers from {lo} to {hi} are written using only the digits {dg}? (Digits may repeat.)",
        opts, idx, expl,
    )


def grid_svg(rows, cols, colored=(), cell=44, col_labels=False, row_labels=False, painted_rows=(), painted_cols=()):
    w = cols * cell
    x0 = (600 - w) / 2
    y0 = 30 if col_labels else 12
    body = []
    for r in range(rows):
        for c in range(cols):
            fill = "#ffffff"
            if (r, c) in colored:
                fill = "#8338ec"
            body.append(
                f'<rect x="{x0 + c * cell:.1f}" y="{y0 + r * cell}" width="{cell}" height="{cell}" fill="{fill}" '
                f'stroke="{INK}" stroke-width="2"/>'
            )
    if col_labels:
        for c in range(cols):
            body.append(text(x0 + c * cell + cell / 2, 14, "ABCDEFGH"[c], size=18))
    if row_labels:
        for r in range(rows):
            body.append(text(x0 - 16, y0 + r * cell + cell / 2, str(r + 1), size=18))
    return svg_doc(600, y0 + rows * cell + 14, "".join(body))


def b_half_grid(p, t):
    rows, cols, colored = p["rows"], p["cols"], set(p["colored"])
    total = rows * cols
    ans = total // 2 - len(colored)
    if ans <= 0 or total % 2:
        raise BuildError("half_grid invalid")
    opts, idx = numeric(ans, t, mistakes=[total // 2, total - len(colored), ans + 1, ans - 1])
    expl = [
        f"Hình có {rows} × {cols} = {total} ô, một nửa là {total} : 2 = {total // 2} ô.",
        f"Đã tô màu {len(colored)} ô.",
        f"Cần tô thêm: {total // 2} − {len(colored)} = {ans} ô.",
    ]
    return make(
        "spatial",
        f"Hình có {total} ô vuông. Bạn Mai đã tô màu một số ô. Cần tô thêm bao nhiêu ô nữa để đúng một nửa số ô được tô màu?",
        f"The picture has {total} squares. Mai has coloured some of them. How many more must she colour so that exactly half are coloured?",
        opts, idx, expl, grid_svg(rows, cols, colored),
    )


def b_paint(p, t):
    rows, cols, prow, pcol = p["rows"], p["cols"], p["rows_painted"], p["cols_painted"]
    ans = (rows - len(prow)) * (cols - len(pcol))
    wrong = rows * cols - len(prow) * cols - len(pcol) * rows
    opts, idx = numeric(ans, t, mistakes=[wrong, ans + 2, ans - 2, ans + cols, len(prow) * cols + len(pcol) * rows])
    rv = join_vi(f"hàng {r}" for r in prow)
    cv = join_vi(f"cột {c}" for c in pcol)
    expl = [
        f"Các ô không bị tô phải nằm ở hàng không tô và cột không tô.",
        f"Số hàng không tô: {rows} − {len(prow)} = {rows - len(prow)}; số cột không tô: {cols} − {len(pcol)} = {cols - len(pcol)}.",
        f"Số ô không tô: {rows - len(prow)} × {cols - len(pcol)} = {ans}.",
        "Chú ý: ô nằm ở chỗ giao nhau của hàng và cột được tô chỉ tính một lần.",
    ]
    return make(
        "spatial",
        f"Bảng có {rows * cols} ô ({rows} hàng, {cols} cột). Sau khi tô màu tất cả các ô ở {rv} cùng với {cv}, có bao nhiêu ô không được tô màu?",
        f"The table has {rows * cols} boxes ({rows} rows, {cols} columns). After painting every box in "
        + ", ".join(f"row {r}" for r in prow) + " and " + ", ".join(f"column {c}" for c in pcol)
        + ", how many boxes are not painted?",
        opts, idx, expl, grid_svg(rows, cols, col_labels=True, row_labels=True),
    )


def b_time(p, t):
    now = p["h"] * 60 + p["m"]
    delta = p["delta"]
    ans = now + delta
    opts, idx = numeric(ans, t, mistakes=[now - delta if delta > 0 else now + abs(delta), ans + 60, ans - 60, ans + 30],
                        step=30, lo=-10_000, fmt=fmt_clock)
    if delta < 0:
        vi = f"Bây giờ là {fmt_clock(now)}. Cách đây {fmt_dur(-delta)} là mấy giờ?"
        en = f"It is now {fmt_clock_en(now)}. What time was it {fmt_dur_en(-delta)} ago?"
        expl = [
            f"Lùi {(-delta) // 60} giờ: {fmt_clock(now)} → {fmt_clock(now - (-delta) // 60 * 60)}.",
            f"Lùi tiếp {(-delta) % 60} phút: {fmt_clock(now - (-delta) // 60 * 60)} → {fmt_clock(ans)}.",
            "Mẹo: vẽ đồng hồ và quay kim ngược chiều để kiểm tra.",
        ]
    else:
        vi = f"Bây giờ là {fmt_clock(now)}. Sau {fmt_dur(delta)} nữa là mấy giờ?"
        en = f"It is now {fmt_clock_en(now)}. What time will it be {fmt_dur_en(delta)} later?"
        expl = [
            f"Thêm {delta // 60} giờ: {fmt_clock(now)} → {fmt_clock(now + delta // 60 * 60)}.",
            f"Thêm tiếp {delta % 60} phút: {fmt_clock(now + delta // 60 * 60)} → {fmt_clock(ans)}.",
            "Chú ý: sau 12 giờ đồng hồ quay lại 1 giờ.",
        ]
    return make("measurement", vi, en, opts, idx, expl)


def b_ages_future(p, t):
    names, s, years = p["names"], p["sum"], p["years"]
    n = len(names)
    ans = s + n * years
    opts, idx = numeric(ans, t, mistakes=[s + years, s + years * 2, ans + 1, ans - 1])
    nm = ", ".join(names[:-1]) + " và " + names[-1]
    expl = [
        f"Sau {years} năm, mỗi bạn đều thêm {years} tuổi.",
        f"Có {n} bạn nên tổng số tuổi tăng thêm {n} × {years} = {n * years}.",
        f"Tổng số tuổi khi đó: {s} + {n * years} = {ans}.",
        f"Chú ý: không phải chỉ cộng thêm {years}.",
    ]
    return make(
        "measurement",
        f"Hôm nay, tuổi của {nm} cộng lại bằng {s}. Sau {years} năm nữa, tổng số tuổi của {n} bạn là bao nhiêu?",
        f"Today the ages of {', '.join(names)} add up to {s}. What will their ages add up to in {years} years?",
        opts, idx, expl,
    )


def b_rabbit(p, t):
    days, carrots, cabbages, cab_total = p["days"], p["carrots"], p["cabbages"], p["cab_total"]
    if cab_total % cabbages:
        raise BuildError("rabbit cabbages")
    cab_days = cab_total // cabbages
    ans = (days - cab_days) * carrots
    opts, idx = numeric(ans, t, mistakes=[days * carrots, cab_days * carrots, ans + carrots, ans - carrots],
                        step=1, lo=1)
    expl = [
        f"Mỗi ngày ăn bắp cải thì ăn {cabbages} cây. Cả tuần ăn {cab_total} cây nên có {cab_total} : {cabbages} = {cab_days} ngày ăn bắp cải.",
        f"Số ngày ăn cà rốt: {days} − {cab_days} = {days - cab_days} ngày.",
        f"Số cà rốt: {days - cab_days} × {carrots} = {ans} củ.",
    ]
    return make(
        "measurement",
        f"Chú thỏ chỉ ăn cà rốt hoặc bắp cải. Mỗi ngày chú ăn hoặc {carrots} củ cà rốt, hoặc {cabbages} cây bắp cải. "
        f"Tuần trước ({days} ngày) chú ăn tất cả {cab_total} cây bắp cải. Tuần trước chú ăn bao nhiêu củ cà rốt?",
        f"A rabbit eats either {carrots} carrots or {cabbages} cabbages each day. Last week ({days} days) it ate {cab_total} cabbages. How many carrots did it eat?",
        opts, idx, expl,
    )


def b_border(p, t):
    e, n = p["example"], p["ask"]
    cell = 28
    side = e + 2
    x0 = (600 - side * cell) / 2
    body = []
    for r in range(side):
        for c in range(side):
            ring = r in (0, side - 1) or c in (0, side - 1)
            body.append(
                f'<rect x="{x0 + c * cell:.1f}" y="{12 + r * cell}" width="{cell}" height="{cell}" '
                f'fill="{"#fb8500" if ring else "#d9d9d9"}" stroke="{INK}" stroke-width="2"/>'
            )
    ans = 4 * n + 4
    opts, idx = numeric(ans, t, mistakes=[4 * n, 4 * n + 2, n * n, ans + 4, ans - 4])
    expl = [
        f"Ở hình mẫu (cạnh {e}): mỗi cạnh có {e} viên, 4 cạnh là 4 × {e} = {4 * e} viên, thêm 4 viên ở 4 góc: {4 * e + 4} viên.",
        f"Với hình vuông cạnh {n}: 4 × {n} = {4 * n} viên dọc 4 cạnh, thêm 4 viên góc.",
        f"Tổng: {4 * n} + 4 = {ans} viên gạch.",
        "Chú ý: đừng quên 4 viên ở các góc.",
    ]
    return make(
        "spatial",
        f"Bạn Nam lát một đường viền bằng các viên gạch vuông nhỏ (màu cam) quanh một hình vuông. "
        f"Hình vẽ cho thấy đường viền quanh hình vuông có cạnh dài {e} viên gạch, dùng {4 * e + 4} viên. "
        f"Cần bao nhiêu viên gạch để lát đường viền quanh hình vuông có cạnh dài {n} viên gạch?",
        f"Nam puts a border of small square tiles (orange) around a square. The picture shows the border around a square of side {e}, using {4 * e + 4} tiles. "
        f"How many tiles are needed for a square of side {n}?",
        opts, idx, expl, svg_doc(600, side * cell + 25, "".join(body)),
    )


def b_encode(p, t):
    grid = p["grid"]
    pos = {}
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch in pos:
                raise BuildError("encode grid letters must be unique")
            pos[ch] = f"{'ABCD'[c]}{r + 1}"
    code = lambda w: " ".join(pos[ch] for ch in w)
    target = p["target"]
    target_code = code(target)
    for w in p["others"]:
        if all(ch in pos for ch in w) and code(w) == target_code:
            raise BuildError("encode distractor collides")
    cell = 46
    x0 = 300 - 2 * cell
    body = []
    for r, row in enumerate(grid):
        body.append(text(x0 - 18, 14 + r * cell + cell / 2, str(r + 1), size=18, fill="#e63946"))
        for c, ch in enumerate(row):
            body.append(f'<rect x="{x0 + c * cell}" y="{14 + r * cell}" width="{cell}" height="{cell}" fill="#ffffff" stroke="{INK}" stroke-width="2"/>')
            body.append(text(x0 + c * cell + cell / 2, 14 + r * cell + cell / 2 + 1, ch, size=22))
    for c in range(4):
        body.append(text(x0 + c * cell + cell / 2, 14 + 4 * cell + 16, "ABCD"[c], size=18, fill="#e63946"))
    opts, idx = place(target, p["others"], t)
    steps = "; ".join(f"{pos[ch]} → {ch}" for ch in target)
    expl = [
        "Mỗi mã gồm chữ của cột (A, B, C, D) và số của hàng (1, 2, 3, 4).",
        f"Giải mã từng phần: {steps}.",
        f"Ghép lại được từ {target}.",
    ]
    ex = p["example"]
    return make(
        "logic",
        f"Bin mã hóa các chữ cái bằng bảng bên. Ví dụ, từ {ex} có mã là {code(ex)}. Bin đã mã hóa từ nào thành {target_code}?",
        f"Bin encodes letters with the board shown. For example, {ex} has the code {code(ex)}. Which word did Bin encode as {target_code}?",
        opts, idx, expl, svg_doc(600, 14 + 4 * cell + 34, "".join(body)),
    )


def b_cookies(p, t):
    cookies, kids = p["cookies"], p["kids"]
    r = cookies % kids
    if r == 0:
        raise BuildError("cookies already divisible")
    ans = kids - r
    opts, idx = numeric(ans, t, mistakes=[r, ans + 1, kids, ans - 1], lo=1)
    nxt = cookies + ans
    expl = [
        f"Muốn chia đều cho {kids} bạn thì số bánh phải chia hết cho {kids}.",
        f"Các số chia hết cho {kids} gần {cookies}: ... {nxt - kids}, {nxt}, ... Số nhỏ nhất không ít hơn {cookies} là {nxt}.",
        f"Cần nướng thêm: {nxt} − {cookies} = {ans} chiếc (mỗi bạn được {nxt // kids} chiếc).",
    ]
    return make(
        "arithmetic",
        f"Bà vừa nướng {cookies} chiếc bánh quy. Bà muốn chia hết số bánh cho {kids} đứa cháu, mỗi cháu được số bánh như nhau. Bà cần nướng thêm ít nhất bao nhiêu chiếc?",
        f"Grandma baked {cookies} cookies. She wants to share all of them equally among {kids} grandchildren. At least how many more must she bake?",
        opts, idx, expl,
    )


def b_glue(p, t):
    cells = set(map(tuple, p["cells"]))
    edges = sum(1 for (r, c) in cells for (dr, dc) in ((0, 1), (1, 0)) if (r + dr, c + dc) in cells)
    rows = max(r for r, _ in cells) + 1
    cols = max(c for _, c in cells) + 1
    cell = 52
    x0 = (600 - cols * cell) / 2
    body = []
    for r, c in sorted(cells):
        body.append(f'<rect x="{x0 + c * cell:.1f}" y="{12 + r * cell}" width="{cell}" height="{cell}" fill="#ffd166" stroke="{INK}" stroke-width="3"/>')
    opts, idx = numeric(edges, t, mistakes=[len(cells), len(cells) - 1, edges + 2, edges - 1, 4 * len(cells)])
    horiz = sum(1 for (r, c) in cells if (r, c + 1) in cells)
    vert = sum(1 for (r, c) in cells if (r + 1, c) in cells)
    expl = [
        "Mỗi chỗ hai tấm bìa chạm nhau bằng một cạnh cần một miếng băng dính.",
        f"Đếm các cạnh chung nằm dọc (giữa hai tấm cạnh nhau theo hàng ngang): {horiz}; các cạnh chung nằm ngang (giữa hai tấm trên – dưới): {vert}.",
        f"Tổng: {horiz} + {vert} = {edges} miếng.",
    ]
    return make(
        "spatial",
        f"Bạn Hà ghép {len(cells)} tấm bìa hình vuông như hình. Ở mỗi chỗ hai tấm bìa chạm nhau bằng cả một cạnh, Hà dán một miếng băng dính. Hà cần bao nhiêu miếng băng dính?",
        f"Ha puts {len(cells)} square cards together as shown. Wherever two cards share a whole side she uses one piece of tape. How many pieces of tape does she need?",
        opts, idx, expl, svg_doc(600, rows * cell + 25, "".join(body)),
    )


def b_order(p, t):
    items, rel, ask = p["items"], p["relations"], p["ask"]
    greater = {(a, b) for a, b in rel}
    changed = True
    while changed:
        changed = False
        for (a, b) in list(greater):
            for (c, d) in list(greater):
                if b == c and (a, d) not in greater:
                    greater.add((a, d))
                    changed = True
    if ask == "max":
        win = [x for x in items if all((x, y) in greater for y in items if y != x)]
    else:
        win = [x for x in items if all((y, x) in greater for y in items if y != x)]
    if len(win) != 1:
        raise BuildError(f"order not determinable: {win}")
    ans = p["display"][win[0]]
    others = [p["display"][x] for x in items if x != win[0]] + p.get("extra", [])
    opts, idx = place(ans, others, t)
    return make("logic", p["vi"], p["en"], opts, idx, p["expl"])


MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def d_en(day, month):
    return f"{MONTHS_EN[month - 1]} {day}"


def b_calendar(p, t):
    s, d, month = p["start"], p["day"], p["month"]
    ans = (s + d - 1) % 7
    same = [x for x in range(1, 32) if (x - 1) % 7 == 0]
    others = [DAYS[(ans + k) % 7] for k in (1, -1, 2, -2)]
    opts, idx = place(DAYS[ans], others, t)
    base = max(x for x in same if x <= d)
    expl = [
        f"Cứ 7 ngày thì thứ lặp lại. Các ngày {', '.join(map(str, same))} tháng {month} đều là {DAYS[s]}.",
        f"Ngày {base} là {DAYS[s]}; ngày {d} sau đó {d - base} ngày.",
        f"Đếm tiếp {d - base} ngày từ {DAYS[s]}: ngày {d} là {DAYS[ans]}.",
    ]
    return make(
        "measurement",
        f"Ngày 1 tháng {month} là {DAYS[s]}. Hỏi ngày {d} tháng {month} là thứ mấy?",
        f"{d_en(1, month)} is a {DAYS_EN[s]}. What day of the week is {d_en(d, month)}?",
        opts, idx, expl,
    )


# =========================================================== Section C (5 đ)

def c_two_kinds(p, t):
    """Camels / chickens-and-dogs / bikes: n items, total of a feature, each item has a or b."""
    n, total, a, b = p["n"], p["total"], p["a"], p["b"]
    if (total - a * n) % (b - a):
        raise BuildError("two_kinds non-integer")
    big = (total - a * n) // (b - a)
    if not (0 < big < n):
        raise BuildError("two_kinds out of range")
    ans = big if p["ask"] == "big" else n - big
    opts, idx = numeric(ans, t, mistakes=[n - ans, total - n, ans + 1, ans - 1])
    expl = [
        f"Giả sử cả {n} {p['unit_vi']} đều là loại có {a} {p['feat_vi']}: khi đó có {a} × {n} = {a * n} {p['feat_vi']}.",
        f"Thực tế có {total} {p['feat_vi']}, thừa ra {total} − {a * n} = {total - a * n}.",
        f"Mỗi {p['unit_vi']} loại {b} {p['feat_vi']} làm thừa thêm {b - a}, nên có {total - a * n} : {b - a} = {big} {p['unit_vi']} loại {b} {p['feat_vi']}.",
        f"Đáp số: {ans}.",
    ]
    return make("arithmetic", p["vi"], p["en"], opts, idx, expl)


def c_ratio_diff(p, t):
    mult, diff = p["mult"], p["diff"]
    if diff % (mult - 1):
        raise BuildError("ratio_diff")
    small = diff // (mult - 1)
    big = small * mult
    ans = small + big
    opts, idx = numeric(ans, t, mistakes=[big, diff * 2, ans + diff, small * 2, ans - 2])
    expl = [
        f"Nếu {p['small_vi']} là 1 phần thì {p['big_vi']} là {mult} phần; {p['big_vi']} nhiều hơn {mult} − 1 = {mult - 1} phần.",
        f"{mult - 1} phần bằng {diff} con, nên 1 phần là {diff} : {mult - 1} = {small} con.",
        f"{p['small_vi'].capitalize()}: {small} con, {p['big_vi']}: {big} con. Tất cả: {small} + {big} = {ans} con.",
    ]
    return make("arithmetic", p["vi"], p["en"], opts, idx, expl)


def c_middle(p, t):
    k = p["k"]
    ans = 2 * k - 1
    opts, idx = numeric(ans, t, mistakes=[2 * k, k, 2 * k + 1, 2 * k - 2])
    expl = [
        f"Người đứng chính giữa là người thứ {k} tính từ đầu, nên phía trước có {k - 1} người.",
        f"Đứng chính giữa nghĩa là phía sau cũng có {k - 1} người.",
        f"Tổng: {k - 1} + 1 + {k - 1} = {ans} người.",
    ]
    return make("arithmetic", p["vi"].format(k=k), p["en"].format(k=k), opts, idx, expl)


def c_flags(p, t):
    n, gap, sides = p["n"], p["gap"], p.get("sides", 1)
    if p["mode"] == "length":
        ans = (n - 1) * gap
        opts, idx = numeric(ans, t, mistakes=[n * gap, (n + 1) * gap, ans - gap // 2], step=gap,
                            fmt=lambda v: f"{v} m")
        expl = [
            f"Có {n} lá cờ thì có {n} − 1 = {n - 1} khoảng cách giữa hai lá liền nhau.",
            f"Độ dài đường chạy: {n - 1} × {gap} = {ans} m.",
            f"Chú ý: số khoảng cách ít hơn số lá cờ 1 (không phải {n} × {gap}).",
        ]
        vi = f"Có {n} lá cờ cắm trên một đường chạy thẳng. Lá cờ đầu tiên ở vạch xuất phát, lá cuối cùng ở vạch đích. Hai lá cờ liền nhau cách nhau {gap} m. Đường chạy dài bao nhiêu mét?"
        en = f"{n} flags stand along a straight track, the first at the start and the last at the finish. Neighbouring flags are {gap} m apart. How long is the track?"
    else:
        length = p["length"]
        per_side = length // gap + 1
        ans = per_side * sides
        opts, idx = numeric(ans, t, mistakes=[length // gap * sides, per_side, ans + sides, ans - 1])
        expl = [
            f"Mỗi bên đường dài {length} m, chia thành {length} : {gap} = {length // gap} khoảng.",
            f"Hai đầu đều có cây nên mỗi bên có {length // gap} + 1 = {per_side} cây.",
            f"Hai bên đường: {per_side} × 2 = {ans} cây.",
        ]
        vi = f"Dọc hai bên một con đường dài {length} m, người ta trồng cây cách đều nhau {gap} m. Ở cả hai đầu đường, mỗi bên đều có một cây. Có tất cả bao nhiêu cây?"
        en = f"Trees are planted along both sides of a {length} m road, {gap} m apart, with a tree at both ends on each side. How many trees are there?"
    return make("logic", vi, en, opts, idx, expl)


def c_erase(p, t):
    N, S = p["N"], p["S"]
    best = None
    for k in range(N, 0, -1):
        for combo in itertools.combinations(range(1, N + 1), k):
            if sum(combo) == S:
                best = (k, combo)
                break
        if best:
            break
    ans, combo = best
    small = sum(range(1, ans + 2))
    opts, idx = numeric(ans, t, mistakes=[ans + 1, ans - 1, ans + 2, N - ans])
    expl = [
        "Muốn còn lại nhiều số nhất thì phải giữ các số nhỏ nhất.",
        f"Nếu giữ {ans + 1} số thì tổng nhỏ nhất là 1 + 2 + ... + {ans + 1} = {small} > {S}, không được.",
        f"Giữ {ans} số được: ví dụ {' + '.join(map(str, combo))} = {S}.",
        f"Vậy còn lại nhiều nhất {ans} số.",
    ]
    return make(
        "arithmetic",
        f"Nam viết các số từ 1 đến {N} lên bảng. Nam xóa đi một số số rồi cộng các số còn lại, được tổng bằng {S}. Trên bảng còn lại nhiều nhất bao nhiêu số?",
        f"Nam writes the numbers 1 to {N} on the board, erases some, and adds the rest to get {S}. At most how many numbers are left?",
        opts, idx, expl,
    )


def c_grid_paths(p, t):
    R, C, blocked = p["rows"], p["cols"], set(map(tuple, p["blocked"]))
    ways = [[0] * C for _ in range(R)]
    for r in range(R):
        for c in range(C):
            if (r, c) in blocked:
                continue
            if r == 0 and c == 0:
                ways[r][c] = 1
            else:
                ways[r][c] = (ways[r - 1][c] if r else 0) + (ways[r][c - 1] if c else 0)
    ans = ways[R - 1][C - 1]
    cell = 62
    x0 = (600 - C * cell) / 2
    body = []
    for r in range(R):
        for c in range(C):
            fill = "#6c757d" if (r, c) in blocked else "#e9f5db"
            body.append(f'<rect x="{x0 + c * cell:.1f}" y="{12 + r * cell}" width="{cell}" height="{cell}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')
    body.append(text(x0 + cell / 2, 12 + cell / 2, "S", size=26, fill="#e63946"))
    body.append(text(x0 + (C - 0.5) * cell, 12 + (R - 0.5) * cell, "Đ", size=26, fill="#2a9d8f"))
    opts, idx = numeric(ans, t, mistakes=[ans + 1, ans - 1, ans + 2, ans * 2])
    table = " | ".join(" ".join("x" if (r, c) in blocked else str(ways[r][c]) for c in range(C)) for r in range(R))
    expl = [
        "Vì chỉ được đi sang phải hoặc đi xuống, số cách đến một ô = số cách đến ô bên trái + số cách đến ô bên trên.",
        "Ô có đá ghi 0 cách. Điền dần từ ô S: " + table + " (mỗi hàng cách nhau bởi |, x là ô đá).",
        f"Ô Đ có {ans} cách.",
    ]
    return make(
        "spatial",
        "Chú chuột đi từ ô S đến ô Đ. Mỗi bước chú chỉ được đi sang phải hoặc đi xuống một ô, và không được đi vào ô có đá (màu xám). Có bao nhiêu đường đi khác nhau?",
        "A mouse goes from S to Đ, each step moving one square right or down, never onto a grey rock. How many different routes are there?",
        opts, idx, expl, svg_doc(600, R * cell + 25, "".join(body)),
    )


def c_frogs(p, t):
    N, a, y = p["N"], p["sang"], p["listened"]
    sang2 = N - y
    sang3 = N - a - sang2
    if sang2 < 0 or sang3 < 0:
        raise BuildError("frogs")
    ans = N - sang3
    opts, idx = numeric(ans, t, mistakes=[sang3, N - a, y, ans + 1, ans - 1], lo=0)
    expl = [
        f"Mỗi đêm có 1 chú hát, 2 chú nghe. Một chú nghe bài hát vào mọi đêm mà chú không hát.",
        f"Chú thứ hai nghe {y} bài nên chú hát {N} − {y} = {sang2} đêm.",
        f"Chú thứ nhất hát {a} đêm, nên chú thứ ba hát {N} − {a} − {sang2} = {sang3} đêm.",
        f"Chú thứ ba nghe vào các đêm còn lại: {N} − {sang3} = {ans} bài.",
    ]
    return make(
        "logic",
        f"Ba chú ếch sống trong một cái ao. Mỗi đêm, đúng một chú ếch hát một bài cho hai chú kia nghe. Sau {N} đêm, một chú ếch đã hát {a} lần, "
        f"một chú khác đã nghe {y} bài hát. Chú ếch thứ ba đã nghe bao nhiêu bài hát?",
        f"Three frogs live in a pond. Each night exactly one frog sings to the other two. After {N} nights one frog has sung {a} times and another has listened to {y} songs. "
        f"How many songs has the third frog listened to?",
        opts, idx, expl,
    )


def c_triangles(p, t):
    cev, hor = p["cevians"], p["horizontals"]
    A = (300.0, 25.0)
    BL, BR = (90.0, 255.0), (510.0, 255.0)
    feet = [(BL[0] + (BR[0] - BL[0]) * (i + 1) / (cev + 1), BL[1]) for i in range(cev)]
    rays = [BL] + feet + [BR]  # apex lines in order left->right
    levels = [A[1] + (BL[1] - A[1]) * (j + 1) / (hor + 1) for j in range(hor)] + [BL[1]]

    def on_ray(i, y):
        bx, by = rays[i]
        s = (y - A[1]) / (by - A[1])
        return (A[0] + (bx - A[0]) * s, y)

    pts = {"apex": A}
    lines_of = {"apex": {("ray", i) for i in range(len(rays))}}
    for j, y in enumerate(levels):
        for i in range(len(rays)):
            key = f"p{i}_{j}"
            pts[key] = on_ray(i, y)
            lines_of[key] = {("ray", i), ("lev", j)}
    keys = list(pts)
    count = 0
    for a, b, c in itertools.combinations(keys, 3):
        la, lb, lc = lines_of[a], lines_of[b], lines_of[c]
        if (la & lb) and (lb & lc) and (la & lc) and not (la & lb & lc):
            count += 1
    formula = math.comb(len(rays), 2) * (hor + 1)
    if count != formula:
        raise BuildError(f"triangle count mismatch {count} vs {formula}")
    body = [poly([A, BL, BR], "#fff3bf")]
    for fx in feet:
        body.append(line(A[0], A[1], fx[0], fx[1], width=3))
    for y in levels[:-1]:
        lx, _ = on_ray(0, y)
        rx, _ = on_ray(len(rays) - 1, y)
        body.append(line(lx, y, rx, y, width=3))
    ans = count
    opts, idx = numeric(ans, t, mistakes=[ans - 2, ans + 2, len(rays) - 1 + hor, ans - len(rays) + 1, ans + 3])
    small = (len(rays) - 1)
    expl = [
        f"Từ đỉnh trên có {len(rays)} đường đi xuống. Hai đường bất kỳ trong số đó cùng với một đường nằm ngang tạo thành một hình tam giác.",
        f"Số cách chọn 2 đường từ {len(rays)} đường: {small} + {small - 1} + ... + 1 = {math.comb(len(rays), 2)}.",
        f"Có {hor + 1} đường nằm ngang (kể cả cạnh đáy), nên có {math.comb(len(rays), 2)} × {hor + 1} = {ans} hình tam giác.",
        "Mẹo: đếm có hệ thống – tam giác nhỏ, rồi tam giác ghép từ 2, 3 phần...",
    ]
    return make(
        "spatial", "Có bao nhiêu hình tam giác trong hình vẽ?", "How many triangles are there in the picture?",
        opts, idx, expl, svg_doc(600, 275, "".join(body)),
    )


def c_cross(p, t):
    nums = p["nums"]
    total = sum(nums)
    valid = []
    for c in nums:
        rest = [x for x in nums if x != c]
        for pair in itertools.combinations(rest, 2):
            other = [x for x in rest if x not in pair]
            if sum(pair) == sum(other):
                valid.append((c, pair, tuple(other)))
                break
    centers = sorted({v[0] for v in valid})
    if len(centers) != 1:
        raise BuildError(f"cross not unique: {centers}")
    ans, pair, other = valid[0]
    pos = [(300, 130), (215, 130), (385, 130), (300, 50), (300, 210)]
    body = [line(215, 130, 385, 130, width=3, color="#adb5bd"), line(300, 50, 300, 210, width=3, color="#adb5bd")]
    for i, (x, y) in enumerate(pos):
        body.append(f'<circle cx="{x}" cy="{y}" r="30" fill="{"#ffe5ec" if i == 0 else "#ffffff"}" stroke="{INK}" stroke-width="3"/>')
    body.append(text(300, 132, "?", size=30, fill="#e63946"))
    opts, idx = numeric(ans, t, mistakes=[x for x in nums if x != ans])
    if not set(map(int, opts)) >= {ans}:
        raise BuildError("cross opts")
    tried = []
    for c in nums:
        rest = [x for x in nums if x != c]
        tried.append(f"giữa là {c}: còn {', '.join(map(str, rest))}" + (" → chia được" if c == ans else " → không chia được thành hai cặp bằng nhau"))
    expl = [
        "Hàng ngang và hàng dọc dùng chung số ở giữa, nên 4 số còn lại phải chia thành 2 cặp có tổng bằng nhau.",
        "Thử từng số ở giữa: " + "; ".join(tried) + ".",
        f"Chỉ khi số giữa là {ans}: {pair[0]} + {pair[1]} = {other[0]} + {other[1]} = {sum(pair)}.",
    ]
    return make(
        "spatial",
        f"Bạn Kiên viết mỗi số {', '.join(map(str, nums))} vào một hình tròn sao cho tổng ba số ở hàng ngang bằng tổng ba số ở hàng dọc. Số nào được viết ở hình tròn chính giữa?",
        f"Kien writes each of {', '.join(map(str, nums))} in a circle so that the row and the column have the same sum. Which number is in the middle circle?",
        opts, idx, expl, svg_doc(600, 255, "".join(body)),
    )


def c_swaps(p, t):
    cards = p["cards"]
    n = len(cards)
    seen, cycles = set(), 0
    for i in range(n):
        if i in seen:
            continue
        cycles += 1
        j = i
        while j not in seen:
            seen.add(j)
            j = cards[j] - 1
    ans = n - cycles
    arr = list(cards)
    steps = []
    for i in range(n):
        if arr[i] != i + 1:
            j = arr.index(i + 1)
            arr[i], arr[j] = arr[j], arr[i]
            steps.append(" ".join(map(str, arr)))
    if len(steps) != ans:
        raise BuildError("swap greedy mismatch")
    body = []
    for i, v in enumerate(cards):
        x = 300 - n * 40 + i * 80
        body.append(f'<rect x="{x + 6}" y="15" width="68" height="90" rx="10" fill="#ffffff" stroke="{INK}" stroke-width="3"/>')
        body.append(text(x + 40, 61, str(v), size=40))
    opts, idx = numeric(ans, t, mistakes=[ans + 1, ans - 1, n, n - 1], lo=1)
    expl = [
        "Mỗi bước đổi chỗ 2 thẻ có thể đưa ít nhất một thẻ về đúng chỗ.",
        "Làm lần lượt: " + " → ".join([" ".join(map(str, cards))] + steps) + f" ({ans} bước).",
        f"Không thể ít hơn {ans} bước vì các thẻ sai chỗ tạo thành {cycles} nhóm vòng; mỗi nhóm k thẻ cần k − 1 lần đổi.",
    ]
    return make(
        "arithmetic",
        "Trên bàn có các tấm thẻ như hình. Mỗi bước, em được đổi chỗ hai tấm thẻ bất kỳ. Cần ít nhất bao nhiêu bước để các thẻ được xếp theo thứ tự từ bé đến lớn?",
        "Cards lie on the table as shown. In each step you may swap any two cards. What is the smallest number of steps to put them in increasing order?",
        opts, idx, expl, svg_doc(600, 120, "".join(body)),
    )


def c_split(p, t):
    T, names, rule, ask = p["T"], p["names"], p["rule"], p["ask"]
    sols = [
        combo for combo in itertools.product(range(1, T), repeat=3)
        if sum(combo) == T and len(set(combo)) == 3 and rule(*combo)
    ]
    if len(sols) != 1:
        raise BuildError(f"split not unique {sols}")
    sol = sols[0]
    ans = sol[names.index(ask)]
    opts, idx = numeric(ans, t, mistakes=[x for x in sol if x != ans] + [ans + 1, ans - 1])
    return make("arithmetic", p["vi"], p["en"], opts, idx, p["expl"](sol))


def c_age_cakes(p, t):
    ages, kids, rule, ask = p["ages"], p["kids"], p["rule"], p["ask"]
    sols = [perm for perm in itertools.permutations(ages) if rule(dict(zip(kids, perm)))]
    if len(sols) != 1:
        raise BuildError(f"age cakes not unique: {len(sols)}")
    sol = dict(zip(kids, sols[0]))
    ans_age = sol[ask]
    order = sorted(a for a in ages if a != ans_age)
    order.insert(t, ans_age)
    body = []
    for i, a in enumerate(order):
        cx = 60 + i * 120
        body.append(f'<rect x="{cx - 38}" y="85" width="76" height="45" rx="8" fill="#f4a261" stroke="{INK}" stroke-width="2"/>')
        body.append(f'<rect x="{cx - 38}" y="85" width="76" height="12" rx="6" fill="#fefae0" stroke="{INK}" stroke-width="2"/>')
        body.append(text(cx, 55, str(a), size=34, fill="#8338ec"))
        body.append(label(cx, 150, LETTERS[i]))
    opts = [f"Bánh {LETTERS[i]}" for i in range(5)]
    return make("logic", p["vi"], p["en"], opts, t, p["expl"](sol), svg_doc(600, 165, "".join(body)))


def c_rooms(p, t):
    nums, walls = p["nums"], {frozenset(map(tuple, w)) for w in p["walls"]}
    R = len(nums)

    def nbrs(r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < R and 0 <= cc < R and frozenset({(r, c), (rr, cc)}) not in walls:
                yield rr, cc

    best = (-1, None)

    def dfs(node, seen, total, path):
        nonlocal best
        if node == (R - 1, R - 1):
            if total > best[0]:
                best = (total, list(path))
        for nb in nbrs(*node):
            if nb not in seen:
                seen.add(nb)
                path.append(nb)
                dfs(nb, seen, total + nums[nb[0]][nb[1]], path)
                path.pop()
                seen.remove(nb)

    dfs((0, 0), {(0, 0)}, nums[0][0], [(0, 0)])
    ans, path = best
    total_all = sum(map(sum, nums))
    if ans == total_all:
        raise BuildError("rooms: best path visits every room, too easy")
    cell = 80
    x0, y0 = 180, 20
    body = []
    for r in range(R):
        for c in range(R):
            body.append(f'<rect x="{x0 + c * cell}" y="{y0 + r * cell}" width="{cell}" height="{cell}" fill="#f1faee"/>')
            body.append(text(x0 + c * cell + cell / 2, y0 + r * cell + cell / 2, str(nums[r][c]), size=30))
    # walls are thick lines; a door is an opening in the middle of a wall
    for r in range(R):
        for c in range(R):
            for dr, dc in ((0, 1), (1, 0)):
                rr, cc = r + dr, c + dc
                if rr >= R or cc >= R:
                    continue
                wall = frozenset({(r, c), (rr, cc)}) in walls
                if dc:
                    x = x0 + cc * cell
                    a, b = (x, y0 + r * cell), (x, y0 + (r + 1) * cell)
                else:
                    y = y0 + rr * cell
                    a, b = (x0 + c * cell, y), (x0 + (c + 1) * cell, y)
                if wall:
                    body.append(line(*a, *b, width=7))
                else:
                    k = 0.3
                    body.append(line(a[0], a[1], a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, width=7))
                    body.append(line(b[0] - (b[0] - a[0]) * k, b[1] - (b[1] - a[1]) * k, b[0], b[1], width=7))
    body.append(f'<rect x="{x0}" y="{y0}" width="{R * cell}" height="{R * cell}" fill="none" stroke="{INK}" stroke-width="7"/>')
    body.append(f'<rect x="{x0 - 4}" y="{y0 + 18}" width="10" height="44" fill="#ffffff"/>')
    body.append(text(x0 - 40, y0 + 40, "Vào →", size=16))
    body.append(f'<rect x="{x0 + R * cell - 6}" y="{y0 + (R - 1) * cell + 18}" width="10" height="44" fill="#ffffff"/>')
    body.append(text(x0 + R * cell + 40, y0 + (R - 1) * cell + 40, "→ Ra", size=16))
    opts, idx = numeric(ans, t, mistakes=[total_all, ans - 2, ans + 2, ans - 1, ans + 1])
    path_txt = " → ".join(str(nums[r][c]) for r, c in path)
    skipped = [nums[r][c] for r in range(R) for c in range(R) if (r, c) not in path]
    expl = [
        "Chỉ đi được qua những chỗ hở trên tường (cửa). Mỗi phòng chỉ đi qua một lần.",
        f"Tổng tất cả các phòng là {total_all}, nhưng không có đường nào đi qua hết mọi phòng.",
        f"Đường tốt nhất: {path_txt}, bỏ qua phòng {', '.join(map(str, skipped))}.",
        f"Tổng lớn nhất: {' + '.join(str(nums[r][c]) for r, c in path)} = {ans}.",
    ]
    return make(
        "spatial",
        "Bé Bi đi từ cửa Vào đến cửa Ra qua các căn phòng. Hai phòng cạnh nhau chỉ thông nhau khi trên bức tường giữa chúng có chỗ hở (cửa). "
        "Mỗi phòng chỉ được đi qua một lần, và Bi cộng các số ở những phòng đã đi qua. Tổng lớn nhất Bi có thể được là bao nhiêu?",
        "Bi walks from the entrance to the exit through the rooms (gaps in the walls are doors), visiting each room at most once and adding the numbers in the rooms. What is the largest possible total?",
        opts, idx, expl, svg_doc(600, R * cell + 40, "".join(body)),
    )


def c_digits(p, t):
    digits = p["digits"]
    best = -1
    best_pair = None
    for a, b, c, d in itertools.permutations(digits):
        if a == 0 or c == 0:
            continue
        s = 10 * a + b + 10 * c + d
        if s > best:
            best, best_pair = s, (10 * a + b, 10 * c + d)
    srt = sorted(digits, reverse=True)
    ans = best
    opts, idx = numeric(ans, t, mistakes=[ans - 9, ans - 18, ans - 1, ans + 9, int("".join(map(str, srt[:2]))) + int("".join(map(str, srt[2:])))])
    expl = [
        "Chữ số ở hàng chục có giá trị gấp 10 lần, nên đặt hai chữ số lớn nhất ở hàng chục.",
        f"Hàng chục: {srt[0]} và {srt[1]}; hàng đơn vị: {srt[2]} và {srt[3]}.",
        f"Ví dụ: {best_pair[0]} + {best_pair[1]} = {ans} (đổi chỗ hai chữ số đơn vị tổng vẫn như vậy).",
    ]
    dg = ", ".join(map(str, digits))
    return make(
        "arithmetic",
        f"Đặt mỗi chữ số {dg} vào một ô trong phép tính □□ + □□ sao cho tổng lớn nhất. Tổng lớn nhất là bao nhiêu?",
        f"Put each of the digits {dg} in a box of □□ + □□ to make the largest sum. What is it?",
        opts, idx, expl,
    )


def c_zebra(p, t):
    a, more, less = p["runa"], p["more"], p["less"]
    zara = a + more
    biba = a + less
    ans = max(a, zara, biba)
    opts, idx = numeric(ans, t, mistakes=[zara, a - less, a + more + less, ans + 1, ans - 1])
    expl = [
        f"Runa có {a} sọc.",
        f"Zara nhiều hơn Runa {more} sọc: {a} + {more} = {zara} sọc.",
        f"Runa ít hơn Biba {less} sọc, nghĩa là Biba nhiều hơn Runa {less} sọc: {a} + {less} = {biba} sọc.",
        f"Nhiều sọc nhất là {ans} sọc.",
        "Chú ý: “Runa ít hơn Biba” nghĩa là Biba nhiều hơn, phải cộng chứ không trừ.",
    ]
    return make(
        "arithmetic",
        f"Ba chú ngựa vằn thi xem ai nhiều sọc nhất. Runa có {a} sọc. Zara có nhiều hơn Runa {more} sọc. Runa có ít hơn Biba {less} sọc. Chú thắng cuộc có bao nhiêu sọc?",
        f"Three zebras compete for the most stripes. Runa has {a}. Zara has {more} more than Runa. Runa has {less} fewer than Biba. How many stripes does the winner have?",
        opts, idx, expl,
    )


def c_handshake(p, t):
    n = p["n"]
    ans = n * (n - 1) // 2
    opts, idx = numeric(ans, t, mistakes=[n * (n - 1), n * n, ans + n, ans - 1])
    terms = " + ".join(str(k) for k in range(n - 1, 0, -1))
    expl = [
        f"Bạn thứ nhất bắt tay {n - 1} bạn còn lại.",
        f"Bạn thứ hai bắt tay thêm {n - 2} bạn mới (đã bắt tay bạn thứ nhất rồi), cứ thế tiếp tục.",
        f"Tổng: {terms} = {ans} cái bắt tay.",
        f"Chú ý: không phải {n} × {n - 1} = {n * (n - 1)}, vì mỗi cái bắt tay bị đếm hai lần.",
    ]
    return make(
        "arithmetic",
        f"Có {n} bạn gặp nhau. Mỗi bạn bắt tay mỗi bạn khác đúng một lần. Có tất cả bao nhiêu cái bắt tay?",
        f"{n} friends meet and each shakes hands with every other friend exactly once. How many handshakes are there?",
        opts, idx, expl,
    )


def c_snail(p, t):
    H, up, down = p["H"], p["up"], p["down"]
    day, pos = 0, 0
    log = []
    while True:
        day += 1
        pos += up
        if pos >= H:
            log.append(f"ngày {day}: bò lên tới {pos} m, chạm đỉnh")
            break
        log.append(f"ngày {day}: lên {pos} m, đêm tụt còn {pos - down} m")
        pos -= down
    ans = day
    naive = math.ceil(H / (up - down))
    opts, idx = numeric(ans, t, mistakes=[naive, ans + 1, ans - 1, H // up])
    expl = [
        f"Mỗi ngày ốc lên {up} m, mỗi đêm tụt {down} m. Nhưng ngày cuối cùng chạm đỉnh là xong, không tụt nữa.",
        "Theo dõi từng ngày: " + "; ".join(log) + ".",
        f"Ốc lên tới đỉnh vào ngày thứ {ans} (không phải {H} : {up - down} = {naive}).",
    ]
    return make(
        "measurement",
        f"Một con ốc sên bò lên một bức tường cao {H} m. Ban ngày ốc bò lên được {up} m, ban đêm ốc tụt xuống {down} m. Bắt đầu từ chân tường vào sáng ngày thứ nhất, ốc lên tới đỉnh tường vào ngày thứ mấy?",
        f"A snail climbs a {H} m wall: up {up} m each day, down {down} m each night. Starting at the bottom on the morning of day 1, on which day does it reach the top?",
        opts, idx, expl,
    )


def c_timespan(p, t):
    sh, sm, eh, em = p["sh"], p["sm"], p["eh"], p["em"]
    start = (sh + 12) * 60 + sm
    end = 24 * 60 + eh * 60 + em
    ans = end - start
    opts, idx = numeric(ans, t, mistakes=[ans + 60, ans - 60, abs((eh * 60 + em) - (sh * 60 + sm)), ans + 120, ans - 120],
                        step=10, lo=10, fmt=fmt_dur)
    to_mid = 24 * 60 - start
    expl = [
        f"Từ {sh} giờ {sm} phút tối đến 12 giờ đêm: {fmt_dur(to_mid)}.",
        f"Từ 12 giờ đêm đến {eh} giờ {em} phút sáng: {fmt_dur(eh * 60 + em)}.",
        f"Tổng: {fmt_dur(to_mid)} + {fmt_dur(eh * 60 + em)} = {fmt_dur(ans)}.",
        "Mẹo: chia chuyến đi thành hai đoạn – trước và sau nửa đêm.",
    ]
    return make(
        "measurement",
        f"Một chuyến tàu đêm khởi hành lúc {sh} giờ {sm} phút tối và đến nơi lúc {eh} giờ {em} phút sáng hôm sau. Chuyến tàu đi hết bao lâu?",
        f"A night train leaves at {sh}:{sm:02d} in the evening and arrives at {eh}:{em:02d} the next morning. How long is the journey?",
        opts, idx, expl,
    )


def c_witch(p, t):
    start = (p["apples"], p["bananas"])
    terminals = set()
    stack = [start]
    seen = set()
    while stack:
        a, b = stack.pop()
        if (a, b) in seen:
            continue
        seen.add((a, b))
        moves = []
        if a >= 3:
            moves.append((a - 3, b + 1))
        if b >= 3:
            moves.append((a + 1, b - 3))
        if not moves:
            terminals.add((a, b))
        stack.extend(moves)
    if len(terminals) != 1:
        raise BuildError(f"witch ambiguous: {terminals}")
    fa, fb = terminals.pop()

    def describe(a, b):
        parts = []
        if a:
            parts.append(f"{a} quả táo")
        if b:
            parts.append(f"{b} quả chuối")
        return " và ".join(parts) or "không còn gì"

    a, b = start
    log = [describe(a, b)]
    while a >= 3 or b >= 3:
        if a >= 3:
            a, b = a - 3, b + 1
        else:
            a, b = a + 1, b - 3
        log.append(describe(a, b))
    ans = describe(fa, fb)
    candidates = [describe(x, y) for x, y in [(1, 0), (0, 1), (0, 2), (1, 1), (2, 0), (1, 2), (2, 1), (0, 3)] if (x, y) != (fa, fb)]
    opts, idx = place(ans, candidates, t)
    expl = [
        "Cứ có 3 quả táo thì đổi thành 1 quả chuối; có 3 quả chuối thì đổi thành 1 quả táo. Đổi đến khi không đổi được nữa.",
        "Theo dõi: " + " → ".join(log) + ".",
        f"Cuối cùng bà còn {ans}.",
    ]
    return make(
        "logic",
        f"Mỗi khi bà phù thủy có 3 quả táo, bà biến chúng thành 1 quả chuối. Mỗi khi bà có 3 quả chuối, bà biến chúng thành 1 quả táo. "
        f"Bà bắt đầu với {describe(*start)} và cứ biến đổi cho đến khi không biến được nữa. Cuối cùng bà còn lại gì?",
        f"Whenever the witch has 3 apples she turns them into 1 banana, and 3 bananas into 1 apple. She starts with {start[0]} apples and {start[1]} bananas "
        f"and keeps going until no change is possible. What does she end with?",
        opts, idx, expl,
    )


def c_candy(p, t):
    ea, eb = p["end_a"], p["end_b"]
    if ea % 2:
        raise BuildError("candy")
    a1, b1 = ea // 2, eb + ea // 2
    if b1 % 2:
        raise BuildError("candy2")
    b0 = b1 // 2
    a0 = a1 + b0
    ask = p["ask"]
    ans = a0 if ask == "a" else b0
    na, nb = p["name_a"], p["name_b"]
    opts, idx = numeric(ans, t, mistakes=[ea, eb, a1, b1, ans + 2, ans - 2])
    expl = [
        "Đi ngược từ cuối lên đầu.",
        f"Lần 2: {nb} cho {na} số kẹo bằng số kẹo {na} đang có, tức là {na} được gấp đôi. Trước lần 2: {na} có {ea} : 2 = {a1}, {nb} có {eb} + {a1} = {b1}.",
        f"Lần 1: {na} cho {nb} số kẹo bằng số kẹo {nb} đang có, tức là {nb} được gấp đôi. Trước lần 1: {nb} có {b1} : 2 = {b0}, {na} có {a1} + {b0} = {a0}.",
        f"Lúc đầu {na} có {a0} viên, {nb} có {b0} viên. Kiểm tra lại theo chiều xuôi là đúng.",
    ]
    who = na if ask == "a" else nb
    return make(
        "arithmetic",
        f"{na} và {nb} trao đổi kẹo. Đầu tiên {na} cho {nb} số kẹo bằng số kẹo {nb} đang có. Sau đó {nb} cho {na} số kẹo bằng số kẹo {na} đang có. "
        f"Cuối cùng {na} có {ea} viên và {nb} có {eb} viên. Lúc đầu {who} có bao nhiêu viên kẹo?",
        f"{na} and {nb} swap sweets. First {na} gives {nb} as many sweets as {nb} has. Then {nb} gives {na} as many as {na} has. "
        f"In the end {na} has {ea} and {nb} has {eb}. How many sweets did {who} have at the start?",
        opts, idx, expl,
    )


def c_trains(p, t):
    n, k, m = p["n"], p["k"], p["m"]
    ans = 2 * k - m
    if not 1 <= ans <= n:
        raise BuildError("trains")
    opts, idx = numeric(ans, t, mistakes=[m, n - m + 1, ans + 1, ans - 1, m - k])
    expl = [
        "Hai đoàn tàu chạy ngược chiều nhau nên khi số toa ở đoàn này tăng thì số toa đối diện ở đoàn kia giảm.",
        f"Toa {k} đối diện toa {k}: tổng hai số là {2 * k}. Mọi cặp toa đối diện đều có tổng bằng {2 * k}.",
        f"Toa {m} đối diện toa {2 * k} − {m} = {ans}.",
    ]
    return make(
        "logic",
        f"Hai đoàn tàu giống hệt nhau, mỗi đoàn có {n} toa đánh số từ 1 đến {n}, chạy ngược chiều nhau trên hai đường ray song song. "
        f"Khi toa số {k} của đoàn này đối diện toa số {k} của đoàn kia thì toa số {m} của đoàn này đối diện toa số mấy?",
        f"Two identical trains with cars numbered 1 to {n} pass each other in opposite directions. When car {k} faces car {k}, which car faces car {m}?",
        opts, idx, expl,
    )


# ================================================================== plans

def rule_vi(text_):
    return text_


EXAMS = [
    # ---------------------------------------------------------------- Đề 1
    [
        (a_count_shapes, dict(kind="triangle", counts={"triangle": 7, "circle": 5, "square": 4}, seed=11)),
        (a_dots, dict(dots=[3, 5, 2, 4, 6])),
        (a_day, dict(mode="yesterday->tomorrow", day=3)),
        (a_queue, dict(n=11, a=4, b=3, x="Lan", y="Minh")),
        (a_cake, dict(big=6, small=7, seed=3, who=("bà", "Grandma"))),
        (a_pattern, dict(unit=["circle", "triangle", "square"], shown=9, k=20)),
        (a_grid_missing, dict(n=5, missing=[(0, 1), (1, 3), (2, 2), (3, 0), (4, 4), (4, 2), (0, 4)])),
        (a_equalize, dict(x=7, y=19, a="An", b="Bình", item_vi="viên bi", item_en="marbles")),
        (b_balance, dict(k1=3, k2=2, e=0)),
        (b_symbols, dict(mode="chain", s1="star", n1=3, v1=4, s2="triangle", v2=7, ask=["triangle", "triangle", "star"])),
        (b_pizza, dict(pizzas=3, slices=6, people=8, each=2)),
        (b_half_grid, dict(rows=4, cols=6, colored=[(0, 0), (0, 3), (1, 1), (1, 4), (2, 2), (2, 5), (3, 0), (3, 3)])),
        (b_time, dict(h=2, m=30, delta=-210)),
        (b_encode, dict(grid=[["M", "E", "O", "T"], ["A", "H", "N", "C"], ["S", "I", "B", "U"], ["K", "R", "D", "L"]],
                        example="MEO", target="HOA", others=["HAO", "HOE", "NOA", "HOI"])),
        (b_glue, dict(cells=[(0, 1), (1, 0), (1, 1), (1, 2), (2, 1), (2, 2)])),
        (b_digits, dict(lo=10, hi=60, digits=[1, 3, 5])),
        (c_two_kinds, dict(n=12, total=17, a=1, b=2, ask="big", unit_vi="con lạc đà", feat_vi="bướu",
                           vi="Trong sở thú có 12 con lạc đà, mỗi con có 1 bướu hoặc 2 bướu. Tổng cộng có 17 cái bướu. Có bao nhiêu con lạc đà 2 bướu?",
                           en="A zoo has 12 camels, each with 1 or 2 humps, 17 humps in total. How many camels have 2 humps?")),
        (c_flags, dict(mode="length", n=9, gap=6)),
        (c_grid_paths, dict(rows=3, cols=4, blocked=[(1, 1)])),
        (c_frogs, dict(N=10, sang=3, listened=6)),
        (c_triangles, dict(cevians=2, horizontals=1)),
        (c_snail, dict(H=10, up=3, down=1)),
        (c_swaps, dict(cards=[3, 1, 2, 5, 4])),
        (c_age_cakes, dict(
            ages=[5, 6, 7, 8, 9], kids=["Hà", "Lan", "Minh", "Tùng", "Vy"], ask="Vy",
            rule=lambda a: a["Lan"] == a["Hà"] + 2 and a["Minh"] == a["Lan"] - 1 and a["Tùng"] == 9 and a["Vy"] != min(a.values()),
            vi="Năm bạn Hà, Lan, Minh, Tùng, Vy có cùng ngày sinh nhật; mỗi bạn có một chiếc bánh với cây nến ghi số tuổi. "
               "Lan hơn Hà 2 tuổi. Minh kém Lan 1 tuổi. Tùng lớn tuổi nhất. Vy không phải là bạn nhỏ tuổi nhất. Bánh nào là của Vy?",
            en="Ha, Lan, Minh, Tung and Vy share a birthday; each cake shows the child's age. Lan is 2 years older than Ha. Minh is 1 year younger than Lan. "
               "Tung is the oldest. Vy is not the youngest. Which cake is Vy's?",
            expl=lambda s: [
                "Tùng lớn tuổi nhất nên Tùng 9 tuổi. Hà, Minh, Lan là ba tuổi liên tiếp (Minh = Hà + 1, Lan = Hà + 2).",
                "Còn lại các tuổi 5, 6, 7, 8 cho Hà, Minh, Lan, Vy. Nếu Hà 6 tuổi thì Vy 5 tuổi là nhỏ nhất – không được.",
                f"Vậy Hà {s['Hà']}, Minh {s['Minh']}, Lan {s['Lan']}, Vy {s['Vy']} tuổi. Bánh của Vy có số {s['Vy']}.",
            ],
        )),
    ],
    # ---------------------------------------------------------------- Đề 2
    [
        (a_most_shape, dict(kind="circle", others=[4, 3, 5, 4], max=6, seed=21)),
        (a_midpoint, dict(a=18, b=46)),
        (a_clock, dict(h=4, m=0, add=90)),
        (a_attr, dict(
            seed=22, target=(2, 3, 1), others=[(1, 3, 1), (3, 2, 1), (2, 4, 1), (3, 4, 3)], noun="Lá cờ",
            rule=lambda c, tr, sq: c > 1 and tr == sq + 2,
            vi="Lá cờ của Bin có nhiều hơn 1 hình tròn, và số hình tam giác nhiều hơn số hình vuông đúng 2 hình. Lá cờ nào là của Bin?",
            en="Bin's flag has more than 1 circle, and exactly 2 more triangles than squares. Which flag is Bin's?",
            why="Lá cờ cần: số hình tròn lớn hơn 1, và số tam giác = số hình vuông + 2.",
        )),
        (a_weight, dict(total=25, mother=18, animal_vi="chó", animal_en="dog")),
        (a_ladybug_fly, dict(others=[4, 2, 5, 3], flyer=6)),
        (a_pattern, dict(unit=["star", "star", "heart", "circle"], shown=10, k=17)),
        (a_count_shapes, dict(kind="circle", counts={"circle": 8, "square": 5, "star": 4}, seed=23)),
        (b_paint, dict(rows=6, cols=5, rows_painted=[2, 5], cols_painted=["B", "D"])),
        (b_order, dict(
            items=["pink", "red", "green", "silver", "yellow"],
            relations=[("red", "yellow"), ("pink", "red"), ("green", "pink"), ("yellow", "silver")],
            ask="max",
            display={"pink": "Tháp hồng", "red": "Tháp đỏ", "green": "Tháp xanh lá", "silver": "Tháp bạc", "yellow": "Tháp vàng"},
            vi="Tháp vàng thấp hơn tháp đỏ. Tháp hồng cao hơn tháp đỏ nhưng thấp hơn tháp xanh lá. Tháp bạc thấp hơn tháp vàng. Tháp nào cao nhất?",
            en="The yellow tower is shorter than the red one. The pink tower is taller than the red but shorter than the green. The silver tower is shorter than the yellow. Which tower is the tallest?",
            expl=[
                "Xếp từ cao xuống thấp theo từng câu: hồng cao hơn đỏ, xanh lá cao hơn hồng → xanh lá > hồng > đỏ.",
                "Vàng thấp hơn đỏ, bạc thấp hơn vàng → đỏ > vàng > bạc.",
                "Ghép lại: xanh lá > hồng > đỏ > vàng > bạc. Tháp xanh lá cao nhất.",
            ],
        )),
        (b_cookies, dict(cookies=17, kids=5)),
        (b_calendar, dict(start=2, day=20, month=5)),
        (b_border, dict(example=2, ask=5)),
        (b_symbols, dict(mode="chain", s1="circle", n1=3, v1=4, s2="square", v2=6, ask=["square", "square", "circle"])),
        (b_rabbit, dict(days=7, carrots=10, cabbages=2, cab_total=8)),
        (b_half_grid, dict(rows=5, cols=4, colored=[(0, 1), (1, 3), (3, 0), (4, 2)])),
        (c_two_kinds, dict(n=12, total=34, a=2, b=4, ask="big", unit_vi="con", feat_vi="chân",
                           vi="Trong sân có gà và chó, tất cả 12 con. Đếm được 34 cái chân. Có bao nhiêu con chó?",
                           en="A yard has chickens and dogs, 12 animals and 34 legs in total. How many dogs are there?")),
        (c_trains, dict(n=25, k=10, m=16)),
        (c_cross, dict(nums=[1, 2, 4, 7, 8])),
        (c_witch, dict(apples=5, bananas=2)),
        (c_timespan, dict(sh=8, sm=15, eh=6, em=40)),
        (c_split, dict(
            T=10, names=["An", "Bình", "Chi"], ask="Chi",
            rule=lambda a, b, c: a < b and a < c and c == 2 * b,
            vi="Ba bạn An, Bình, Chi hái được tất cả 10 quả cam. Mỗi bạn hái được ít nhất 1 quả và không có hai bạn nào hái được số quả bằng nhau. "
               "An hái được ít nhất. Chi hái được gấp đôi Bình. Chi hái được bao nhiêu quả?",
            en="An, Binh and Chi picked 10 oranges, each at least 1 and all different. An picked the fewest. Chi picked twice as many as Binh. How many did Chi pick?",
            expl=lambda s: [
                "Chi gấp đôi Bình nên Bình + Chi = 3 phần (Bình 1 phần, Chi 2 phần), An = 10 − 3 phần.",
                "Thử Bình = 1: Chi 2, An 7 – An không ít nhất. Bình = 2: Chi 4, An 4 – trùng nhau. Bình = 3: Chi 6, An 1 – đúng!",
                f"Vậy An {s[0]}, Bình {s[1]}, Chi {s[2]} quả.",
            ],
        )),
        (c_rooms, dict(nums=[[2, 6, 3], [5, 1, 8], [4, 7, 2]], walls=[[(0, 1), (1, 1)], [(1, 1), (1, 2)], [(1, 0), (2, 0)]])),
        (c_middle, dict(k=9,
                        vi="Các bạn xếp hàng lên xe buýt. Cô giáo đứng chính giữa hàng và là người thứ {k} tính từ đầu hàng. Hàng có bao nhiêu người?",
                        en="Children queue for the bus. The teacher stands exactly in the middle and is {k}th from the front. How many people are in the queue?")),
    ],
    # ---------------------------------------------------------------- Đề 3
    [
        (a_grid_missing, dict(n=4, missing=[(0, 0), (1, 2), (2, 1), (3, 3), (3, 1)])),
        (a_largest_below, dict(n=20, exprs=["9 + 9", "25 − 4", "12 + 7", "30 − 10", "6 + 11"])),
        (a_ages, dict(a=6, diff=5, name="Tí")),
        (a_queue, dict(n=15, a=6, b=4, x="Mai", y="Hoa")),
        (a_clock, dict(h=9, m=30, add=30)),
        (a_attr, dict(
            seed=32, target=(1, 3, 2), others=[(2, 3, 1), (1, 2, 3), (2, 3, 2), (1, 4, 3)], noun="Thẻ",
            rule=lambda c, tr, sq: tr == 3 and c < sq,
            vi="Thẻ của Na có đúng 3 hình tam giác, và số hình tròn ít hơn số hình vuông. Thẻ nào là của Na?",
            en="Na's card has exactly 3 triangles, and fewer circles than squares. Which card is Na's?",
            why="Thẻ cần: đúng 3 hình tam giác, và số hình tròn nhỏ hơn số hình vuông.",
        )),
        (a_dots, dict(dots=[6, 1, 5, 3, 2, 4])),
        (a_most_shape, dict(kind="square", others=[3, 4, 2, 4], max=5, seed=33)),
        (b_balance, dict(k1=2, k2=3, e=1)),
        (b_encode, dict(grid=[["C", "A", "T", "O"], ["L", "U", "N", "G"], ["B", "I", "E", "S"], ["H", "R", "M", "D"]],
                        example="LUA", target="SEN", others=["SAN", "SON", "BEN", "SET"])),
        (b_digits, dict(lo=10, hi=50, digits=[0, 2, 4])),
        (b_glue, dict(cells=[(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2)])),
        (b_ages_future, dict(names=["Bo", "Bi", "Bống"], sum=21, years=3)),
        (b_order, dict(
            items=["An", "Binh", "Chi", "Dung"],
            relations=[("An", "Binh"), ("Binh", "Chi"), ("Dung", "An")],
            ask="min",
            display={"An": "An", "Binh": "Bình", "Chi": "Chi", "Dung": "Dũng"},
            extra=["Không xác định được"],
            vi="An cao hơn Bình. Chi thấp hơn Bình. Dũng cao hơn An. Bạn nào thấp nhất?",
            en="An is taller than Binh. Chi is shorter than Binh. Dung is taller than An. Who is the shortest?",
            expl=[
                "Dũng cao hơn An, An cao hơn Bình → Dũng > An > Bình.",
                "Chi thấp hơn Bình → Dũng > An > Bình > Chi.",
                "Chi thấp nhất.",
            ],
        )),
        (b_pizza, dict(pizzas=4, slices=6, people=9, each=2)),
        (b_border, dict(example=3, ask=6)),
        (c_ratio_diff, dict(mult=3, diff=12, small_vi="vịt", big_vi="gà",
                            vi="Trong chuồng có gà và vịt. Số gà gấp 3 lần số vịt, và gà nhiều hơn vịt 12 con. Trong chuồng có tất cả bao nhiêu con?",
                            en="A pen has hens and ducks. There are 3 times as many hens as ducks, and 12 more hens than ducks. How many birds are there?")),
        (c_flags, dict(mode="trees", n=0, gap=5, length=30, sides=2)),
        (c_triangles, dict(cevians=3, horizontals=0)),
        (c_frogs, dict(N=12, sang=5, listened=9)),
        (c_snail, dict(H=12, up=4, down=2)),
        (c_candy, dict(end_a=8, end_b=8, ask="a", name_a="Tom", name_b="Lily")),
        (c_digits, dict(digits=[1, 2, 4, 5])),
        (c_trains, dict(n=20, k=7, m=11)),
    ],
    # ---------------------------------------------------------------- Đề 4
    [
        (a_count_shapes, dict(kind="star", counts={"star": 6, "heart": 5, "triangle": 6}, seed=41)),
        (a_equalize, dict(x=12, y=30, a="Hùng", b="Dũng", item_vi="nhãn dán", item_en="stickers")),
        (a_stairs, dict(S=10, a=3, b=2)),
        (a_pattern, dict(unit=["heart", "square", "square", "triangle", "circle"], shown=10, k=23)),
        (a_cake, dict(big=7, small=4, seed=4, who=("ông", "Grandpa"))),
        (a_ladybug_fly, dict(others=[5, 3, 6, 2], flyer=4)),
        (a_day, dict(mode="daybefore->dayafter", day=4)),
        (a_grid_missing, dict(n=5, missing=[(0, 2), (1, 0), (1, 4), (2, 3), (3, 1), (4, 2)])),
        (b_half_grid, dict(rows=3, cols=8, colored=[(0, 0), (0, 5), (1, 2), (1, 6), (2, 1), (2, 4), (2, 7)])),
        (b_symbols, dict(mode="two", s1="heart", n1=3, v1=4, s2="circle", n2=2, v2=7, ask=["heart", "heart", "circle"])),
        (b_cookies, dict(cookies=38, kids=7)),
        (b_calendar, dict(start=6, day=25, month=10)),
        (b_paint, dict(rows=5, cols=6, rows_painted=[1, 4, 5], cols_painted=["C"])),
        (b_encode, dict(grid=[["G", "A", "H", "K"], ["O", "N", "I", "T"], ["E", "M", "U", "B"], ["R", "S", "C", "L"]],
                        example="MUA", target="BONG", others=["BONT", "BANG", "LONG", "BOGN"])),
        (b_time, dict(h=10, m=30, delta=150)),
        (b_glue, dict(cells=[(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 1)])),
        (c_erase, dict(N=10, S=20)),
        (c_age_cakes, dict(
            ages=[4, 5, 6, 7, 8], kids=["An", "Bình", "Chi", "Dung", "Em"], ask="Em",
            rule=lambda a: a["Bình"] == a["An"] + 3 and a["Chi"] < a["An"] and a["Dung"] == a["Bình"] - 2,
            vi="Năm bạn An, Bình, Chi, Dung, Em có cùng ngày sinh nhật; mỗi bạn có một chiếc bánh với cây nến ghi số tuổi. "
               "Bình hơn An 3 tuổi. Chi nhỏ tuổi hơn An. Dung kém Bình 2 tuổi. Bánh nào là của Em?",
            en="An, Binh, Chi, Dung and Em share a birthday; each cake shows the child's age. Binh is 3 years older than An. Chi is younger than An. "
               "Dung is 2 years younger than Binh. Which cake is Em's?",
            expl=lambda s: [
                "Chi nhỏ hơn An nên An không thể 4 tuổi. Bình = An + 3 ≤ 8 nên An ≤ 5. Vậy An 5 tuổi, Bình 8 tuổi.",
                "Dung = Bình − 2 = 6 tuổi. Chi nhỏ hơn An: Chi 4 tuổi.",
                f"Tuổi còn lại là {s['Em']}: bánh của Em có số {s['Em']}.",
            ],
        )),
        (c_grid_paths, dict(rows=4, cols=4, blocked=[(1, 2), (2, 0)])),
        (c_witch, dict(apples=7, bananas=0)),
        (c_timespan, dict(sh=7, sm=30, eh=5, em=50)),
        (c_two_kinds, dict(n=9, total=22, a=2, b=3, ask="big", unit_vi="chiếc xe", feat_vi="bánh",
                           vi="Ở bãi giữ xe có 9 chiếc xe gồm xe đạp (2 bánh) và xe ba bánh. Đếm được tất cả 22 bánh xe. Có bao nhiêu chiếc xe ba bánh?",
                           en="A bike park has 9 bicycles and tricycles with 22 wheels in total. How many tricycles are there?")),
        (c_cross, dict(nums=[1, 4, 5, 6, 8])),
        (c_handshake, dict(n=6)),
    ],
    # ---------------------------------------------------------------- Đề 5
    [
        (a_most_shape, dict(kind="triangle", others=[5, 3, 4, 6], max=7, seed=51)),
        (a_midpoint, dict(a=24, b=52)),
        (a_weight, dict(total=95, mother=78, animal_vi="gấu", animal_en="bear")),
        (a_queue, dict(n=14, a=3, b=5, x="Bin", y="Na")),
        (a_clock, dict(h=11, m=0, add=90)),
        (a_attr, dict(
            seed=52, target=(3, 2, 1), others=[(2, 2, 2), (3, 2, 2), (1, 3, 2), (4, 1, 2)], noun="Tranh",
            rule=lambda c, tr, sq: c + tr + sq == 6 and c > tr,
            vi="Bức tranh của Tú có tất cả 6 hình, trong đó số hình tròn nhiều hơn số hình tam giác. Bức tranh nào là của Tú?",
            en="Tu's picture has 6 shapes in total, with more circles than triangles. Which picture is Tu's?",
            why="Tranh cần: tổng cộng đúng 6 hình, và số hình tròn nhiều hơn số hình tam giác.",
        )),
        (a_largest_below, dict(n=30, exprs=["16 + 13", "41 − 10", "18 + 9", "35 − 5", "22 + 6"])),
        (a_count_shapes, dict(kind="square", counts={"square": 9, "triangle": 6, "circle": 3}, seed=53)),
        (b_balance, dict(k1=4, k2=2, e=0)),
        (b_order, dict(
            items=["red", "blue", "yellow", "purple", "black"],
            relations=[("red", "blue"), ("blue", "yellow"), ("purple", "red"), ("purple", "black"), ("black", "red")],
            ask="max",
            display={"red": "Bút đỏ", "blue": "Bút xanh", "yellow": "Bút vàng", "purple": "Bút tím", "black": "Bút đen"},
            vi="Bút đỏ dài hơn bút xanh. Bút vàng ngắn hơn bút xanh. Bút tím dài hơn bút đỏ. Bút đen ngắn hơn bút tím nhưng dài hơn bút đỏ. Bút nào dài nhất?",
            en="The red pen is longer than the blue. The yellow pen is shorter than the blue. The purple pen is longer than the red. The black pen is shorter than the purple but longer than the red. Which pen is the longest?",
            expl=[
                "Tím > đen > đỏ (đen ngắn hơn tím nhưng dài hơn đỏ).",
                "Đỏ > xanh > vàng.",
                "Ghép lại: tím > đen > đỏ > xanh > vàng. Bút tím dài nhất.",
            ],
        )),
        (b_pizza, dict(pizzas=3, slices=8, people=10, each=2)),
        (b_border, dict(example=2, ask=7)),
        (b_rabbit, dict(days=7, carrots=5, cabbages=3, cab_total=9)),
        (b_symbols, dict(mode="chain", s1="square", n1=2, v1=5, s2="triangle", v2=8, ask=["triangle", "triangle", "square"])),
        (b_digits, dict(lo=20, hi=60, digits=[1, 2, 5])),
        (b_paint, dict(rows=4, cols=7, rows_painted=[2], cols_painted=["A", "D", "G"])),
        (c_rooms, dict(nums=[[4, 3, 9], [1, 8, 2], [6, 5, 3]], walls=[[(0, 0), (1, 0)], [(1, 1), (2, 1)], [(0, 2), (1, 2)]])),
        (c_frogs, dict(N=11, sang=4, listened=7)),
        (c_triangles, dict(cevians=1, horizontals=2)),
        (c_candy, dict(end_a=12, end_b=10, ask="a", name_a="John", name_b="Mai")),
        (c_snail, dict(H=15, up=5, down=3)),
        (c_erase, dict(N=12, S=30)),
        (c_age_cakes, dict(
            ages=[6, 7, 8, 9, 10], kids=["Phúc", "Quân", "Sơn", "Tâm", "Uyên"], ask="Uyên",
            rule=lambda a: a["Phúc"] == a["Quân"] - 2 and a["Sơn"] == a["Quân"] + 2 and a["Tâm"] > a["Uyên"],
            vi="Năm bạn Phúc, Quân, Sơn, Tâm, Uyên có cùng ngày sinh nhật; mỗi bạn có một chiếc bánh với cây nến ghi số tuổi. "
               "Phúc kém Quân 2 tuổi. Sơn hơn Quân 2 tuổi. Tâm lớn tuổi hơn Uyên. Bánh nào là của Uyên?",
            en="Phuc, Quan, Son, Tam and Uyen share a birthday; each cake shows the child's age. Phuc is 2 years younger than Quan. Son is 2 years older than Quan. "
               "Tam is older than Uyen. Which cake is Uyen's?",
            expl=lambda s: [
                "Phúc, Quân, Sơn cách nhau đều 2 tuổi: Quân − 2, Quân, Quân + 2. Với các tuổi 6 đến 10 chỉ có thể là 6, 8, 10.",
                "Còn lại 7 và 9 cho Tâm và Uyên. Tâm lớn hơn Uyên nên Tâm 9 tuổi, Uyên 7 tuổi.",
                f"Bánh của Uyên có số {s['Uyên']}.",
            ],
        )),
        (c_ratio_diff, dict(mult=2, diff=9, small_vi="bò", big_vi="cừu",
                            vi="Trang trại chỉ có cừu và bò. Số bò bằng một nửa số cừu, và cừu nhiều hơn bò 9 con. Trang trại có tất cả bao nhiêu con?",
                            en="A farm has only sheep and cows. There are half as many cows as sheep, and 9 more sheep than cows. How many animals are there?")),
    ],
]


def build():
    questions = []
    templates = []
    letter_stats = {}
    for e, plan in enumerate(EXAMS, start=1):
        if len(plan) != 24:
            raise BuildError(f"exam {e} has {len(plan)} questions")
        rng = random.Random(1000 + e)
        targets = [0, 1, 2, 3, 4] * 5
        rng.shuffle(targets)
        out_dir = IMG_ROOT / f"e{e}"
        out_dir.mkdir(parents=True, exist_ok=True)
        ids = []
        topics = {}
        for i, (fn, params) in enumerate(plan, start=1):
            q = fn(params, targets[i - 1])
            opts = q["options"]
            if len(opts) != 5 or len(set(opts)) != 5:
                raise BuildError(f"e{e} q{i}: options invalid {opts}")
            if not 0 <= q["answer"] < 5:
                raise BuildError(f"e{e} q{i}: answer index")
            section, points = ("A", 3) if i <= 8 else ("B", 4) if i <= 16 else ("C", 5)
            qid = f"ai-e{e}-q{i:02d}"
            image_url = None
            if q["svg"]:
                (out_dir / f"q{i:02d}.svg").write_text(q["svg"], encoding="utf-8")
                image_url = f"/question-images/ai/e{e}/q{i:02d}.svg"
            letter = LETTERS[q["answer"]]
            letter_stats.setdefault(e, {}).setdefault(letter, 0)
            letter_stats[e][letter] += 1
            topics[q["topic"]] = topics.get(q["topic"], 0) + 1
            questions.append({
                "id": qid,
                "canonical_hash": qid,
                "source_id": "src-ai-v1",
                "source_question_number": (e - 1) * 24 + i,
                "source_page": 1,
                "year": None,
                "section": section,
                "points": points,
                "topic": q["topic"],
                "stem": q["en"],
                "stem_vi": q["vi"],
                "image_url": image_url,
                "correct_option": letter,
                "explanation": q["expl"],
                "status": "published",
                "answer_verified": True,
                "answer_source": f"AI generate: đáp án tính bằng code ({fn.__name__}), đã kiểm tra lại bằng lời giải độc lập",
                "origin": "ai",
                "options": [
                    {"key": LETTERS[k], "text": opts[k], "image_url": None, "sort_order": k + 1}
                    for k in range(5)
                ],
            })
            ids.append(qid)
        templates.append({
            "id": f"tpl-ai-{e:02d}", "slug": f"de-ai-{e}", "title": f"Đề AI số {e}",
            "position": 100 + e, "tag": "ai_generated", "question_ids": ids,
        })
        print(f"Đề AI {e}: topics={topics} letters={dict(sorted(letter_stats[e].items()))}")

    stems = [q["stem_vi"] + "|" + "|".join(o["text"] for o in q["options"]) for q in questions]
    if len(set(stems)) != len(stems):
        raise BuildError("duplicate question across exams")

    payload = {
        "version": 1,
        "source": {
            "id": "src-ai-v1", "slug": "ai-generate-v1", "title": "AI generate · Bộ đề thử nghiệm", "year": None,
            "language": "bilingual", "kind": "practice", "source_pdf_url": "", "page_count": 1,
            "question_count": len(questions), "review_status": "reviewed",
        },
        "templates": templates,
        "questions": questions,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(questions)} questions, {len(templates)} templates -> {OUT}")


if __name__ == "__main__":
    build()
