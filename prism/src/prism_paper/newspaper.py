"""Vertical newspaper typesetting from saved originals; no forecast generation."""
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import fitz
from PIL import Image, ImageChops

INK = (0.07, 0.12, 0.18)
RED = (0.65, 0.07, 0.12)
PAPER = (1, 0.993, 0.97)
WIDTH, HEIGHT = 842, 1191
BET_NAMES = {"WIN": "単勝", "PLACE": "複勝", "QUINELLA": "馬連", "EXACTA": "馬単", "WIDE": "ワイド", "TRIO": "三連複", "TRIFECTA": "三連単"}


def compact(text):
    return re.sub(r"\s+", "", str(text))


def comparison_text(text):
    # CJK fonts can map a shared glyph to its Unicode compatibility character.
    # Normalize only the comparison, retaining the original source for layout.
    return unicodedata.normalize("NFKC", compact(text)).translate({0x2010: ord("-"), 0x2011: ord("-")})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return "未公表" if value is None else str(value)


class Newspaper:
    def __init__(self, payload, font_file):
        self.payload = payload
        self.doc = fitz.open()
        self.font_file = str(font_file)
        self.font = fitz.Font(fontfile=self.font_file)
        self.chunks = []
        self.orientation = []
        self.font_size = 10.5
        self.band = 0
        self.cursor = 0
        self.section = ""

    def vertical(self, page, text, right, top, width, height, size=10.5, color=INK):
        value = compact(text)
        rows = int(height // (size * 1.10))
        cols = int(width // (size * 1.32))
        if not rows or len(value) > rows * cols:
            raise ValueError(f"vertical text exceeds reserved area: {value[:30]}")
        for index, char in enumerate(value):
            if not self.font.has_glyph(ord(char)):
                raise ValueError(f"font lacks source character: {char}")
            column, row = divmod(index, rows)
            x = right - size * 1.32 * column - size
            y = top + size + size * 1.10 * row
            page.insert_text((x, y), char, fontname="prism-jp", fontsize=size, color=color)
        if value:
            self.chunks.append(value)
            self.orientation.append({"page": page.number + 1, "characters": len(value), "vertical": True})
        return math.ceil(len(value) / rows) * size * 1.32

    def page(self, title, front=False):
        page = self.doc.new_page(width=WIDTH, height=HEIGHT)
        page.insert_font(fontname="prism-jp", fontfile=self.font_file)
        page.draw_rect(page.rect, color=None, fill=PAPER)
        page.draw_line((29, 25), (WIDTH - 29, 25), color=INK, width=3)
        page.draw_line((29, HEIGHT - 38), (WIDTH - 29, HEIGHT - 38), color=INK, width=1)
        self.vertical(page, "PRISM競馬新聞", WIDTH - 31, 36, 32, 210 if front else 130, 20 if front else 12)
        self.vertical(page, title, WIDTH - 88, 37, 380, 200 if front else 107, 26 if front else 17, RED)
        if not front:
            self.vertical(page, f"{self.payload['card']['race_date']}　{self.payload['card']['race_name']}　{page.number + 1}面",
                          350, 37, 315, 107, 10)
        self.band = 0
        self.cursor = WIDTH - 35
        return page

    def front(self):
        card = self.payload["card"]
        page = self.page(card["race_name"], front=True)
        runners = [r for r in card["runners"] if r.get("status") not in ("SCRATCHED", "EXCLUDED")]
        records = self.payload["forecast"]["records"]
        paper = next(r for r in records if r["forecaster_id"] == "HONSHI")
        top = paper["picks"][0]["horse_name"] if paper["picks"] else "判断保留"
        self.vertical(page, f"本紙参考◎{top}", 600, 55, 155, 185, 20, RED)
        top_reason = next((row["reason"] for row in paper["diagnoses"] if row["horse_name"] == top), paper.get("skip_reason") or "判断保留")
        self.vertical(page, f"本紙の比較理由。{top_reason}", 270, 45, 220, 185, 12)
        course = card["course"]
        surface = {"TURF": "芝", "DIRT": "ダート", "JUMP": "障害", "BANEI": "ばんえい"}[course["surface"]]
        self.vertical(page, f"{surface}{course['distance_m']}米　発走{card['off_at'][11:16]}　出走{len(runners)}頭",
                      430, 55, 145, 185, 12)
        span = (WIDTH - 70) / len(runners)
        for index, horse in enumerate(sorted(runners, key=lambda r: r.get("horse_no") or r["horse_id"])):
            right = WIDTH - 35 - span * index
            page.draw_rect(fitz.Rect(right - span, 258, right, 1030), color=(0.4, 0.4, 0.4), width=.4)
            frame = horse.get("frame_no")
            colors = {1: (1, 1, 1), 2: (.1, .1, .1), 3: (.8, .1, .1), 4: (.1, .35, .7),
                      5: (.95, .85, .15), 6: (.15, .6, .35), 7: (.95, .55, .15), 8: (.9, .4, .65)}
            page.draw_rect(fitz.Rect(right - span, 258, right, 326), color=None, fill=colors.get(frame, (.9, .9, .9)))
            self.vertical(page, f"{number(frame)}枠{number(horse.get('horse_no'))}番", right - 2, 261, span - 5, 60, 9,
                          (1, 1, 1) if frame in (2, 3, 4, 6) else INK)
            self.vertical(page, horse["horse_name"], right - 3, 341, 20, 650, 11.5)
            details = [f"騎手{horse.get('jockey_name') or '未公表'}", f"斤量{number(horse.get('carried_weight'))}",
                       f"単勝{number(horse.get('win_odds'))}倍", f"父{horse.get('pedigree', {}).get('sire') or '未収録'}"]
            for run in (horse.get("history") or [])[:4]:
                details.append(f"{run.get('date')}　{run.get('venue') or ''}　{number(run.get('distance_m'))}米　"
                               f"{number(run.get('finish'))}着／{number(run.get('field_size'))}頭　"
                               f"上がり{number(run.get('last_3f'))}秒")
            self.vertical(page, "。".join(details), right - 23, 341, span - 26, 650, 8)
        self.vertical(page, "編集部暫定版。独立AIの未実行は次面以降に明記。参考印は保存された担当別計算から掲載。",
                      WIDTH - 35, 1050, WIDTH - 70, 90, 10)

    def flow(self, title, paragraphs):
        total = sum(len(compact(heading + text)) for heading, text in paragraphs) + 18 * len(paragraphs)
        self.font_size = 10.5 if title.startswith("編集座談会") else max(10.5, min(15, .95 * math.sqrt(280 * (WIDTH - 70) * 3 / (1.10 * 1.32 * max(total, 1)))))
        page = self.page(title)
        self.section = title
        for heading, text in paragraphs:
            value = compact(f"{heading}　{text}")
            while value:
                top = 169 + self.band * 320
                available_cols = int((self.cursor - 35) // (self.font_size * 1.32))
                if available_cols < 3:
                    self.band += 1
                    self.cursor = WIDTH - 35
                    if self.band >= 3:
                        page = self.page(title + "続")
                    else:
                        page.draw_line((35, top + 300), (WIDTH - 35, top + 300), color=INK, width=.5)
                    continue
                rows = int(280 // (self.font_size * 1.10))
                take = min(len(value), available_cols * rows)
                chunk = value[:take]
                used = self.vertical(page, chunk, self.cursor, top, self.cursor - 35, 280, self.font_size)
                self.cursor -= used + self.font_size * .45
                value = value[take:]

    def render(self):
        p = self.payload
        records = p["forecast"]["records"]
        paper = next(row for row in records if row["forecaster_id"] == "HONSHI")
        self.front()
        diagnoses = []
        for row in paper["diagnoses"]:
            comments = []
            for method in ("course", "sectional", "pace"):
                record = next(item for item in records if item["execution"]["method"] == method)
                comment = next(item for item in record["diagnoses"] if item["horse_name"] == row["horse_name"])
                comments.append(f"{record['specialty']}の参考評価。{comment['reason']}")
            diagnoses.append((f"{number(row.get('horse_no'))}番　{row['horse_name']}",
                              f"本紙参考印{row.get('mark') or '無印'}。{row['reason']}。" + "。".join(comments)))
        self.flow("全頭診断", diagnoses)
        paragraphs = []
        for record, execution in zip(records, p["executions"], strict=True):
            marks = "、".join(f"{row['mark']}{row['horse_name']}" for row in record["picks"]) or "判断保留"
            reason = next((row["reason"] for row in record["diagnoses"]
                           if record["picks"] and row["horse_name"] == record["picks"][0]["horse_name"]), record.get("skip_reason") or "")
            tickets = "、".join(f"{BET_NAMES[row['type']]}{','.join(map(str, row['horse_nos']))}番各百円" for row in record["tickets"]) or "買い目は見送り"
            paragraphs.append((record["display_name"], f"{record['specialty']}。{execution['label']}。{marks}。{reason}。紙上参考・{tickets}。"))
        self.flow("本紙・担当別の結論", paragraphs)
        self.flow("判断の根拠と情報の範囲", [
            ("資料の取得", f"JRA・NAR公式出馬表。取得日時{p['card']['captured_at']}。枠番と馬番は別に保持。単勝値は取得時点の掲載値。"),
            ("予想の保存", f"保存日時{p['forecast']['saved_at']}。この紙面は保存済みの原本を掲載し、未実行AIの独立予想を作っていません。"),
            ("専門資料の確認", "映像・調教・厩舎取材・当日馬場・気象・学習の資料がない担当は、原本の不足理由と見送りを掲載しています。"),
            ("座談会の区分", "巻末は保存された一次予想を基にした自動編集の座談会です。独立AI同士の実対話や学習完了の実績ではありません。"),
            *[(row["horse_name"], "。".join(f"{r.get('date')}・{r.get('race_name') or r.get('venue')}・{number(r.get('finish'))}着・上がり{number(r.get('last_3f'))}秒"
                                             for r in (row.get("history") or [])[:4]) or "掲載済み過去走資料なし。")
              for row in p["card"]["runners"] if row.get("status") not in ("SCRATCHED", "EXCLUDED")],
        ])
        self.flow("編集座談会・五議題", [(topic["title"] + "／" + turn["name"], turn["text"])
                     for topic in p["roundtable"]["topics"] for turn in topic["turns"]])
        return self.doc


def render_newspaper(payload, output, font_file):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paper = Newspaper(payload, font_file)
    document = paper.render()
    pdf = output / "PRISM_M_PAPER.pdf"
    document.save(pdf, deflate=True)
    document.close()
    pngs = []
    with fitz.open(pdf) as reopened:
        for index, page in enumerate(reopened):
            path = output / f"PRISM_M_PAPER_{index + 1:02d}.png"
            page.get_pixmap(dpi=120, alpha=False).save(path)
            pngs.append(path)
    layout = {"schema": "prism.newspaper_layout/v1", "writing_mode": "vertical-rl",
              "source_forecast_sha256": payload["original_forecast_sha256"],
              "text_chunks": paper.chunks, "orientation": paper.orientation}
    (output / "layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    return pdf, pngs, layout


def verify_newspaper(payload, pdf, pngs, layout):
    failures = []
    document = fitz.open(pdf)
    text = comparison_text("".join(page.get_text() for page in document))
    if not document.page_count or document.page_count != len(pngs):
        failures.append("PDF_PNG_PAGE_COUNT_MISMATCH")
    for chunk in layout["text_chunks"]:
        if comparison_text(chunk) not in text:
            failures.append("BODY_TEXT_MISSING:" + chunk[:35])
    for horse in payload["forecast"]["runners"]:
        if comparison_text(horse["horse_name"]) not in text:
            failures.append("HORSE_NAME_MISSING:" + horse["horse_name"])
    for page in document:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    box = fitz.Rect(span["bbox"])
                    if not page.rect.contains(box):
                        failures.append(f"TEXT_OUTSIDE_PAGE:{page.number + 1}")
    if layout.get("writing_mode") != "vertical-rl" or not all(row["vertical"] for row in layout["orientation"]):
        failures.append("NON_VERTICAL_BODY")
    artifacts = [{"path": str(pdf), "bytes": Path(pdf).stat().st_size, "sha256": sha(pdf)}]
    for page, path in zip(document, pngs, strict=True):
        with Image.open(path) as image:
            image.load()
            fresh = page.get_pixmap(dpi=120, alpha=False)
            expected = Image.frombytes("RGB", (fresh.width, fresh.height), fresh.samples)
            if image.mode != "RGB" or image.size != expected.size or ImageChops.difference(image, expected).getbbox():
                failures.append("PNG_DIFFERS_FROM_PDF:" + str(path))
            if not ImageChops.difference(image, Image.new("RGB", image.size, image.getpixel((0, 0)))).getbbox():
                failures.append("BLANK_PNG:" + str(path))
        artifacts.append({"path": str(path), "bytes": Path(path).stat().st_size, "sha256": sha(path)})
    document.close()
    return {"schema": "prism.newspaper_qa/v1", "passed": not failures, "failures": failures,
            "pages": len(pngs), "text_chunks_checked": len(layout["text_chunks"]),
            "writing_mode": layout["writing_mode"], "artifacts": artifacts}
