#!/usr/bin/env python3
"""Build the production question seed from source PDFs.

Runtime requirements for this ingestion tool (not the web/API container):
- poppler: pdfinfo, pdftoppm, pdftotext
- tesseract (eng)
- Pillow

Published pool: official 2014–2022 questions with independently verified keys.
Other questions are imported as needs_review and are never served for scoring.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "public/exams"
LIBRARY_INDEX = ROOT / "public/exams/index.json"
IMAGE_ROOT = ROOT / "public/question-images"
SEED_PATH = ROOT / "server/data/questions.seed.json"
TRANSLATION_DIR = ROOT / "server/data/translations"

ANSWER_KEYS: dict[int, str] = {
    2014: "BDCBECBEDDBCDDAADD",
    2015: "DCBCBEBECBCCAEDEDDDCCAAD",
    2016: "DDBBCDABDCEADBEAEC",
    2017: "EDACADDEBABDDCBEEA",
    2018: "DDDBBBDAECEBECABED",
    2019: "DACCEBCCEBDABBEDEDADBCDA",
    2020: "DEAEADEDCCECBABDDDCCBECB",
    2021: "EBADADEBDDCEACBDDACCBCEC",
    2022: "BEBBDBBEAEADADCCDAEDCCAC",
}

EXPECTED_COUNTS = {2014: 18, 2015: 24, 2016: 18, 2017: 18, 2018: 18, 2019: 24, 2020: 24, 2021: 24, 2022: 24}
ANSWER_SOURCES = {
    2014: "Answer Key embedded in 2014Grade0102.pdf, page 6",
    2015: "IKMC official answer key f71e0d21e5aaa5fbe204e049c6fac295.pdf",
    2016: "Answer Key embedded in 2016Grade0102.pdf, page 6",
    2017: "Answer Key embedded in IKMC Grade1-2 2017.pdf, page 8",
    2018: "Answer Key embedded in IKMC 2018 1.2.pdf, page 8",
    2019: "IKMC official answer key f348a868aab7d5a64ea2c656ef2cf90f.pdf",
    2020: "IKMC official answer key 0-Answer_Key_IKMC_2020.pdf",
    2021: "IKMC official answer key b-Answer_Key_IKMC_2021.pdf",
    2022: "IKMC official answer key a-Answer_Key_IKMC_2022.pdf",
}

VECTOR_PAGE_MAP: dict[int, dict[int, list[int]]] = {
    2014: {2: [1, 2, 3, 4], 3: [5, 6, 7, 8, 9], 4: [10, 11, 12, 13, 14], 5: [15, 16, 17, 18]},
    2015: {1: [1, 2, 3], 2: [4, 5], 3: [6, 7, 8], 4: [9, 10, 11, 12], 5: [13, 14, 15, 16], 6: [17, 18, 19, 20], 7: [21, 22, 23, 24]},
    2016: {1: [1, 2, 3, 4, 5, 6], 2: [7, 8, 9, 10], 3: [11, 12, 13], 4: [14, 15, 16], 5: [17, 18]},
    2017: {2: [1, 2, 3], 3: [4, 5, 6, 7], 4: [8, 9, 10, 11], 5: [12, 13, 14], 6: [15, 16], 7: [17, 18]},
    2018: {2: [1, 2, 3], 3: [4, 5, 6], 4: [7, 8, 9, 10], 5: [11, 12, 13], 6: [14, 15, 16], 7: [17, 18]},
    2019: {1: [1, 2, 3, 4, 5], 2: [6, 7, 8, 9], 3: [10, 11, 12], 4: [13, 14, 15], 5: [16, 17, 18, 19], 6: [20, 21, 22, 23, 24]},
}

SCAN_MANUAL_POSITIONS: dict[int, dict[int, tuple[int, int]]] = {
    2020: {9: (4, 250)},
    2021: {16: (5, 1950), 19: (6, 1780)},
    2022: {9: (3, 1380), 19: (6, 1350)},
}


def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(args, check=True, **kwargs)


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def normalize_hash(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def find_pdf(year: int) -> Path:
    matches = [p for p in PDF_DIR.glob("*.pdf") if str(year) in p.name and "Tong" not in p.name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one PDF for {year}, got {matches}")
    return matches[0]


def doc_for_year(index: dict[str, Any], year: int) -> dict[str, Any]:
    return next(d for d in index["documents"] if d["year"] == year)


def question_meta(number: int, count: int) -> tuple[str, int]:
    group = 6 if count == 18 else 8
    if number <= group:
        return "A", 3
    if number <= group * 2:
        return "B", 4
    return "C", 5


def classify_topic(text: str) -> str:
    t = text.lower()
    if re.search(r"clock|hour|minute|day|week|month|year|cm|km|metre|meter|weight|weigh|heavy|light|calendar|time", t):
        return "measurement"
    if re.search(r"triangle|square|rectangle|cube|shape|figure|fold|mirror|rotate|symmetr|grid|tile|piece|block|brick|picture", t):
        return "spatial"
    if re.search(r"sum|number|digit|add|subtract|plus|minus|count|how many|sequence|equal|double|half|total", t):
        return "arithmetic"
    return "logic"


def parse_options(raw: str) -> tuple[str, list[dict[str, Any]]]:
    flat = re.sub(r"\s+", " ", raw).strip()
    markers = list(re.finditer(r"\(([A-E])\)", flat))
    values: dict[str, str | None] = {key: None for key in "ABCDE"}
    first_option = len(flat)
    if markers:
        first_option = markers[0].start()
        for i, marker in enumerate(markers):
            key = marker.group(1)
            end = markers[i + 1].start() if i + 1 < len(markers) else len(flat)
            value = flat[marker.end():end].strip(" :-–—")[:600]
            values[key] = value or None
    stem = flat[:first_option]
    stem = re.sub(r"^(?:SECTION|Part)\s+[^0-9]*", "", stem, flags=re.I)
    stem = re.sub(r"^\s*\d{1,2}[.)]\s*", "", stem).strip()
    options = [
        {"key": key, "text": values[key], "image_url": None, "sort_order": i + 1}
        for i, key in enumerate("ABCDE")
    ]
    return stem or flat[:2000], options


def render_pages(pdf: Path, pages: set[int], target: Path, scan: bool) -> dict[int, Image.Image]:
    result: dict[int, Image.Image] = {}
    for page in sorted(pages):
        prefix = target / f"page-{page}"
        run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "180", "-png", "-singlefile", str(pdf), str(prefix)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        image = Image.open(str(prefix) + ".png").convert("RGB")
        if scan and image.width < 1800:
            # Some official scans embed a low-resolution page image; upscale for
            # legibility only. Do NOT autocontrast/enhance-contrast here: those ops
            # are per-channel and visibly distort colors on colorful diagrams (this
            # is what produced the washed-out/mis-colored 2021 exam crops before it
            # was caught and fixed by re-rendering without this step).
            scale = 1800 / image.width
            image = image.resize((1800, int(image.height * scale)), Image.Resampling.LANCZOS)
        result[page] = image
    return result


def vector_positions(pdf: Path, page_map: dict[int, list[int]], images: dict[int, Image.Image], target: Path) -> dict[int, tuple[int, int]]:
    positions: dict[int, tuple[int, int]] = {}
    for page, numbers in page_map.items():
        bbox = target / f"bbox-{page}.html"
        run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox-layout", str(pdf), str(bbox)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = ET.parse(bbox).getroot()
        page_node = next(node for node in root.iter() if node.tag.endswith("page"))
        page_height = float(page_node.attrib["height"])
        words = [node for node in root.iter() if node.tag.endswith("word")]
        for q in numbers:
            hits = [w for w in words if (w.text or "").strip() in (f"{q}.", f"{q})")]
            if not hits:
                raise RuntimeError(f"Missing bbox for {pdf.name} q{q} page {page}")
            word = min(hits, key=lambda w: (float(w.attrib["xMin"]), float(w.attrib["yMin"])))
            y = int(float(word.attrib["yMin"]) / page_height * images[page].height)
            positions[q] = (page, y)
    return positions


def scan_positions(images: dict[int, Image.Image], year: int, target: Path) -> dict[int, tuple[int, int]]:
    candidates: dict[int, list[tuple[int, int, int]]] = {q: [] for q in range(1, 25)}
    for page, image in images.items():
        prep = target / f"ocr-{page}.png"
        ImageOps.grayscale(image).save(prep)
        output = subprocess.check_output(["tesseract", str(prep), "stdout", "-l", "eng", "--psm", "6", "tsv"], stderr=subprocess.DEVNULL).decode(errors="ignore")
        for row in csv.DictReader(io.StringIO(output), delimiter="\t"):
            token = (row.get("text") or "").strip()
            left = int(row.get("left") or 99999)
            top = int(row.get("top") or 0)
            if left > 500:
                continue
            for q in range(1, 25):
                if re.match(rf"^{q}[.)](?:$|[^0-9])", token):
                    candidates[q].append((page, top, left))
    positions: dict[int, tuple[int, int]] = {}
    previous = (0, 0)
    for q in range(1, 25):
        valid = [item for item in candidates[q] if (item[0], item[1]) > previous]
        if valid:
            page, top, _ = min(valid, key=lambda item: (item[0], item[1]))
            positions[q] = (page, top)
            previous = (page, top)
    positions.update(SCAN_MANUAL_POSITIONS[year])
    if set(positions) != set(range(1, 25)):
        raise RuntimeError(f"Incomplete positions for {year}: missing {set(range(1,25)) - set(positions)}")
    ordered = [positions[q] for q in range(1, 25)]
    if ordered != sorted(ordered):
        raise RuntimeError(f"Non-monotonic positions for {year}: {ordered}")
    return positions


def combine_question_image(images: dict[int, Image.Image], start: tuple[int, int], end: tuple[int, int] | None) -> Image.Image:
    start_page, start_y = start
    end_page, end_y = end if end else (start_page, images[start_page].height - 70)
    pieces: list[Image.Image] = []
    for page in range(start_page, end_page + 1):
        image = images[page]
        top = max(0, start_y - 22) if page == start_page else 80
        bottom = min(image.height, end_y - 14) if page == end_page else image.height - 70
        if bottom > top + 30:
            pieces.append(image.crop((25, top, image.width - 25, bottom)))
    if not pieces:
        raise RuntimeError(f"Empty crop from {start} to {end}")
    width = max(piece.width for piece in pieces)
    height = sum(piece.height for piece in pieces) + (len(pieces) - 1) * 8
    result = Image.new("RGB", (width, height), "#e2e8f0")
    y = 0
    for piece in pieces:
        result.paste(piece, (0, y))
        y += piece.height + 8
    return result


def page_region_text(doc: dict[str, Any], positions: dict[int, tuple[int, int]], q: int, count: int) -> str:
    start_page, _ = positions[q]
    end = positions.get(q + 1)
    chunks: list[str] = []
    for page in range(start_page, (end[0] if end else start_page) + 1):
        text = doc["pages"][page - 1]["text"]
        if page == start_page:
            match = re.search(rf"(?m)^\s*{q}[.)]\s*", text)
            text = text[match.start():] if match else text
        if end and page == end[0]:
            next_match = re.search(rf"(?m)^\s*{q + 1}[.)]\s*", text)
            if next_match:
                text = text[:next_match.start()]
        chunks.append(text)
    return "\n".join(chunks).strip()


def ocr_image(image: Image.Image, target: Path) -> str:
    temp = target / "question-ocr.png"
    gray = ImageOps.grayscale(image)
    if gray.width > 1900:
        scale = 1900 / gray.width
        gray = gray.resize((1900, int(gray.height * scale)), Image.Resampling.LANCZOS)
    gray.save(temp)
    return subprocess.check_output(["tesseract", str(temp), "stdout", "-l", "eng", "--psm", "6"], stderr=subprocess.DEVNULL).decode(errors="ignore").strip()


def concat_pages(doc: dict[str, Any]) -> tuple[str, list[tuple[int, int, int]]]:
    parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    offset = 0
    for page in doc["pages"]:
        text = page["text"] + "\n"
        parts.append(text)
        spans.append((offset, offset + len(text), page["page"]))
        offset += len(text)
    return "".join(parts), spans


def page_at(offset: int, spans: list[tuple[int, int, int]]) -> int:
    return next(page for start, end, page in spans if start <= offset < end)


def sequential_segments(section: str, base_offset: int, spans: list[tuple[int, int, int]], count: int, pattern_template: str) -> list[tuple[int, str, int]]:
    matches: list[re.Match[str]] = []
    cursor = 0
    for expected in range(1, count + 1):
        pattern = re.compile(pattern_template.format(q=expected), re.M)
        match = pattern.search(section, cursor)
        if not match:
            raise RuntimeError(f"Missing sequential question {expected}")
        matches.append(match)
        cursor = match.end()
    result = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        raw = section[match.start():end].strip()
        result.append((i + 1, raw, page_at(base_offset + match.start(), spans)))
    return result


def main() -> None:
    index = json.loads(LIBRARY_INDEX.read_text())
    translations: dict[str, str] = {}
    for translation_file in sorted(TRANSLATION_DIR.glob("*.json")):
        values = json.loads(translation_file.read_text(encoding="utf-8"))
        overlap = set(translations) & set(values)
        if overlap:
            raise RuntimeError(f"Duplicate translation keys in {translation_file}: {sorted(overlap)[:3]}")
        translations.update(values)
    for year, count in EXPECTED_COUNTS.items():
        if len(ANSWER_KEYS[year]) != count or set(ANSWER_KEYS[year]) - set("ABCDE"):
            raise RuntimeError(f"Invalid answer key {year}: {ANSWER_KEYS[year]} ({len(ANSWER_KEYS[year])})")

    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    canonical: dict[str, dict[str, Any]] = {}

    # 192 verified official questions with authoritative per-question crops.
    for year, count in EXPECTED_COUNTS.items():
        pdf = find_pdf(year)
        doc = doc_for_year(index, year)
        source_id = f"src-{year}"
        sources.append({
            "id": source_id, "slug": f"ikmc-{year}", "title": doc["title"], "year": year,
            "language": "en", "kind": "official", "source_pdf_url": doc["pdfUrl"],
            "page_count": doc["pageCount"], "question_count": count, "review_status": "reviewed",
        })
        scan = year >= 2020
        page_map = VECTOR_PAGE_MAP.get(year)
        page_set = set(page_map) if page_map else set(range(1, 9))
        output_dir = IMAGE_ROOT / str(year)
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_name:
            temp = Path(temp_name)
            page_images = render_pages(pdf, page_set, temp, scan)
            positions = scan_positions(page_images, year, temp) if scan else vector_positions(pdf, page_map or {}, page_images, temp)
            for q in range(1, count + 1):
                end = positions.get(q + 1)
                image = combine_question_image(page_images, positions[q], end)
                image_path = output_dir / f"q{q:02d}.webp"
                image.save(image_path, "WEBP", quality=88, method=6)
                raw = ocr_image(image, temp) if scan else page_region_text(doc, positions, q, count)
                stem, options = parse_options(raw)
                section, points = question_meta(q, count)
                question_id = f"ikmc-{year}-q{q:02d}"
                item = {
                    "id": question_id, "canonical_hash": normalize_hash(stem), "source_id": source_id,
                    "source_question_number": q, "source_page": positions[q][0], "year": year,
                    "section": section, "points": points, "topic": classify_topic(stem), "stem": stem,
                    "stem_vi": translations.get(question_id), "image_url": f"/question-images/{year}/q{q:02d}.webp",
                    "correct_option": ANSWER_KEYS[year][q - 1], "explanation": [],
                    "status": "published", "answer_verified": True, "answer_source": ANSWER_SOURCES[year],
                    "options": options,
                }
                questions.append(item)
                canonical[question_id] = item
                provenance.append({"question_id": question_id, "source_id": source_id, "source_question_number": q, "source_page": positions[q][0], "raw_text": raw})
        print(f"Official {year}: {count} published")

    # Collection: 10 exams / 240 occurrences. Link known duplicate questions to
    # the verified canonical rows; create needs_review rows for the remaining 120.
    collection = next(d for d in index["documents"] if d["kind"] == "collection")
    full, spans = concat_pages(collection)
    headings = list(re.finditer(r"(?m)^\s*ĐỀ SỐ\s+(\d+):", full))
    years = [2009, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019]
    for i, heading in enumerate(headings):
        year = years[i]
        start = heading.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(full)
        section_text = full[start:end]
        segments = sequential_segments(section_text, start, spans, 24, r"^\s*{q}\.\s+")
        source_id = f"src-collection-{year}"
        sources.append({
            "id": source_id, "slug": f"collection-{year}", "title": f"IKMC {year} · bản tổng hợp song ngữ",
            "year": year, "language": "bilingual", "kind": "collection", "source_pdf_url": collection["pdfUrl"],
            "page_count": collection["pageCount"], "question_count": 24, "review_status": "pending",
        })
        verified_count = EXPECTED_COUNTS.get(year, 0)
        for q, raw, page in segments:
            duplicate_id = f"ikmc-{year}-q{q:02d}"
            if q <= verified_count and duplicate_id in canonical:
                question_id = duplicate_id
            else:
                question_id = f"collection-{year}-q{q:02d}"
                stem, options = parse_options(raw)
                section_name, points = question_meta(q, 24)
                item = {
                    "id": question_id, "canonical_hash": normalize_hash(stem), "source_id": source_id,
                    "source_question_number": q, "source_page": page, "year": year, "section": section_name,
                    "points": points, "topic": classify_topic(stem), "stem": stem, "stem_vi": None,
                    "image_url": None, "correct_option": None, "explanation": [], "status": "needs_review",
                    "answer_verified": False, "answer_source": None, "options": options,
                }
                questions.append(item)
                canonical[question_id] = item
            provenance.append({"question_id": question_id, "source_id": source_id, "source_question_number": q, "source_page": page, "raw_text": raw})

    # Practice PDF: 50 selected questions + 50 topic exercises. Both remain
    # needs_review because the supplied answer column is blank.
    practice = next(d for d in index["documents"] if d["kind"] == "practice")
    full, spans = concat_pages(practice)
    part1_start = full.index("PHẦN 1:")
    part2_start = full.index("PHẦN 2:")
    practice_parts = [
        ("selected", "50 câu tuyển chọn", full[part1_start:part2_start], part1_start, r"^\s*{q}\.\s+"),
        ("topics", "50 bài theo chủ đề", full[part2_start:], part2_start, r"^\s*{q}\s+(?=\S)"),
    ]
    for slug, title, section_text, offset, pattern in practice_parts:
        source_id = f"src-practice-{slug}"
        sources.append({
            "id": source_id, "slug": f"practice-{slug}", "title": title, "year": None,
            "language": "vi", "kind": "practice", "source_pdf_url": practice["pdfUrl"],
            "page_count": practice["pageCount"], "question_count": 50, "review_status": "pending",
        })
        segments = sequential_segments(section_text, offset, spans, 50, pattern)
        for q, raw, page in segments:
            question_id = f"practice-{slug}-q{q:02d}"
            stem, options = parse_options(raw)
            item = {
                "id": question_id, "canonical_hash": normalize_hash(stem), "source_id": source_id,
                "source_question_number": q, "source_page": page, "year": None, "section": "A",
                "points": 3, "topic": classify_topic(stem), "stem": stem, "stem_vi": stem,
                "image_url": None, "correct_option": None, "explanation": [], "status": "needs_review",
                "answer_verified": False, "answer_source": None, "options": options,
            }
            questions.append(item)
            canonical[question_id] = item
            provenance.append({"question_id": question_id, "source_id": source_id, "source_question_number": q, "source_page": page, "raw_text": raw})

    published_ids = {item["id"] for item in questions if item["status"] == "published"}
    translation_ids = set(translations)
    missing_translations = published_ids - translation_ids
    extra_translations = translation_ids - published_ids
    empty_translations = {key for key, value in translations.items() if not isinstance(value, str) or not value.strip()}
    if missing_translations or extra_translations or empty_translations:
        raise RuntimeError(
            f"Invalid translations: missing={sorted(missing_translations)}, "
            f"extra={sorted(extra_translations)}, empty={sorted(empty_translations)}"
        )

    payload = {
        "version": 1,
        "summary": {
            "sources": len(sources), "canonical_questions": len(questions), "provenance_records": len(provenance),
            "published": sum(q["status"] == "published" for q in questions),
            "needs_review": sum(q["status"] == "needs_review" for q in questions),
        },
        "sources": sources, "questions": questions, "provenance": provenance,
    }
    SEED_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
