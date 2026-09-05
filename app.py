"""PW3 dashboard demo renderer and read-only HTTP state.

The prototype deliberately keeps the data contract small and fixture-driven. It
does not know about Kindle credentials, Apple accounts, NAS services, or agents.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import json
import os
import re
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont


VERSION = "0.1.0"
WIDTH = 1072
HEIGHT = 1448
LANDSCAPE_WIDTH = 1448
LANDSCAPE_HEIGHT = 1072
GRAY_LEVELS = 16
PALETTE = tuple(round(i * 255 / (GRAY_LEVELS - 1)) for i in range(GRAY_LEVELS))
FONT_CANDIDATES = (
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
)


DEFAULT_FIXTURE: dict[str, Any] = {
    "date": "2026-08-29",
    "weekday": "星期六",
    "lunar": "农历七月十七 · 丙午马年 · 处暑",
    "lunar_note": "示意",
    "solar_term": "处暑",
    "next_solar_term": "白露",
    "almanac": {"宜": "阅读 · 整理", "忌": "久坐 · 熬夜"},
    "next_item": {"time": "09:30", "title": "家庭周末计划会", "detail": "书房 · 线上"},
    "events": [
        {"time": "09:30", "title": "家庭周末计划会", "detail": "书房 · 线上"},
        {"time": "14:00", "title": "整理番茄小说更新", "detail": "个人 · 阅读"},
        {"time": "19:30", "title": "晚间散步与照片整理", "detail": "附近公园"},
    ],
    "tasks": [
        {"time": "10:45", "title": "确认 Kindle 看板的今日内容", "detail": "今天"},
        {"time": "16:00", "title": "把长标题换行后再检查显示边界", "detail": "今天"},
        {"time": "20:30", "title": "这是一条很长的待办示例，用来验证在 PW3 窄屏上会安全换行并在达到行数上限后截断", "detail": "本周"},
    ],
    "future_events": [
        {"date": "08月29日", "weekday": "六", "time": "09:30", "title": "家庭周末计划会", "kind": "日程"},
        {"date": "08月30日", "weekday": "日", "time": "10:00", "title": "整理番茄小说更新", "kind": "待办"},
        {"date": "08月31日", "weekday": "一", "time": "19:30", "title": "晚间散步与照片整理", "kind": "日程"},
        {"date": "09月01日", "weekday": "二", "time": "16:00", "title": "检查看板长标题与边界", "kind": "待办"},
    ],
    "news": [
        {"title": "今日信息由本地 fixture 提供，未连接真实账号或在线新闻源。"},
        {"title": "看板服务端只生成图片和小型 manifest，设备端负责主动拉取与缓存。"},
        {"title": "后续可接入 Agent 卡片，但不会把个人令牌写入 Kindle。"},
    ],
    "weather": {"location": "上海", "condition": "多云", "temperature": "27°C", "high_low": "22° / 30°"},
    "photo_caption": "每日图片占位 · 等待本地照片适配",
    "sync_status": "演示数据 · 只读 · 最近同步 08:45",
}

_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def load_fixture(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        return json.loads(json.dumps(DEFAULT_FIXTURE, ensure_ascii=False))
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = []
    configured = os.environ.get("KINDLE_FONT_PATH")
    if configured:
        candidates.append(configured)
    candidates.extend(FONT_CANDIDATES)
    for candidate in candidates:
        if not Path(candidate).exists():
            continue
        try:
            font = ImageFont.truetype(candidate, size=size, index=0)
            _FONT_CACHE[key] = font
            return font
        except OSError:
            continue
    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def clean_text(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def truncate_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> str:
    text = clean_text(text)
    if draw.textlength(text, font=font) <= width:
        return text
    suffix = "…"
    while text and draw.textlength(text + suffix, font=font) > width:
        text = text[:-1]
    return (text.rstrip() + suffix) if text else suffix


def force_ellipsis(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> str:
    text = clean_text(text).rstrip("。；， ")
    suffix = "…"
    while text and draw.textlength(text + suffix, font=font) > width:
        text = text[:-1]
    return (text.rstrip() + suffix) if text else suffix


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    width: int,
    max_lines: int | None = None,
) -> list[str]:
    """Wrap by measured glyph width and ellipsize at the line boundary."""
    source = str(text or "").replace("\r", "")
    lines: list[str] = []
    for paragraph in source.split("\n") or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            if not current or draw.textlength(candidate, font=font) <= width:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current or not lines:
            lines.append(current)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = force_ellipsis(draw, lines[-1], font, width)
    return lines


def draw_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    width: int,
    font: ImageFont.ImageFont,
    fill: int = 16,
    line_gap: int = 12,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_text(draw, text, font, width, max_lines=max_lines)
    bbox = draw.textbbox((x, y), "国", font=font)
    line_height = max(1, bbox[3] - bbox[1]) + line_gap
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def prepare_data(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Normalize empty/oversized fixture data into a safe display payload."""
    source = raw if isinstance(raw, dict) else {}
    degraded: list[str] = []

    def item_list(key: str, fallback: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
        value = source.get(key)
        if not isinstance(value, list) or not value:
            degraded.append(f"{key}_empty")
            return fallback
        normalized: list[dict[str, str]] = []
        for item in value[:limit]:
            if not isinstance(item, dict):
                continue
            normalized.append({k: clean_text(item.get(k), 240) for k in item.keys()})
        if not normalized:
            degraded.append(f"{key}_invalid")
            return fallback
        if len(value) > limit:
            degraded.append(f"{key}_limited")
        return normalized

    events = item_list("events", [{"time": "--:--", "title": "暂无日程", "detail": "保持弹性"}], 4)
    tasks = item_list("tasks", [{"time": "--:--", "title": "暂无待办", "detail": "今天"}], 4)
    news = item_list("news", [{"title": "暂无简报", "detail": "稍后重试"}], 3)
    weather = source.get("weather") if isinstance(source.get("weather"), dict) else {}
    if not weather:
        degraded.append("weather_empty")
    weather = {
        "location": clean_text(weather.get("location", "未知地点"), 40),
        "condition": clean_text(weather.get("condition", "暂无天气"), 40),
        "temperature": clean_text(weather.get("temperature", "--"), 20),
        "high_low": clean_text(weather.get("high_low", "--"), 30),
    }
    next_item = source.get("next_item") if isinstance(source.get("next_item"), dict) else events[0]
    future_source = source.get("future_events")
    future_fallback = [
        {"date": "08月29日", "weekday": "六", "time": "09:30", "title": events[0].get("title", "暂无安排"), "kind": "日程"},
        {"date": "08月30日", "weekday": "日", "time": "10:00", "title": "整理番茄小说更新", "kind": "待办"},
        {"date": "08月31日", "weekday": "一", "time": "19:30", "title": "晚间散步与照片整理", "kind": "日程"},
    ]
    if not isinstance(future_source, list) or not future_source:
        degraded.append("future_events_empty")
        future_source = future_fallback
    future_events: list[dict[str, str]] = []
    for item in future_source[:5]:
        if not isinstance(item, dict):
            continue
        future_events.append({
            "date": clean_text(item.get("date", "--月--日"), 20),
            "weekday": clean_text(item.get("weekday", "-"), 8),
            "time": clean_text(item.get("time", "--:--"), 12),
            "title": clean_text(item.get("title", "暂无安排"), 240),
            "kind": clean_text(item.get("kind", "日程"), 12),
        })
    if not future_events:
        degraded.append("future_events_invalid")
        future_events = future_fallback
    almanac = source.get("almanac") if isinstance(source.get("almanac"), dict) else {}
    result = {
        "date": clean_text(source.get("date", "----年--月--日"), 24),
        "weekday": clean_text(source.get("weekday", ""), 12),
        "lunar": clean_text(source.get("lunar", "农历信息暂无"), 80),
        "lunar_note": clean_text(source.get("lunar_note", "示意"), 12),
        "solar_term": clean_text(source.get("solar_term", "节气暂无"), 20),
        "next_solar_term": clean_text(source.get("next_solar_term", "下一节气暂无"), 20),
        "almanac": {"宜": clean_text(almanac.get("宜", "暂无"), 30), "忌": clean_text(almanac.get("忌", "暂无"), 30)},
        "next_item": {"time": clean_text(next_item.get("time", "--:--"), 12), "title": clean_text(next_item.get("title", "暂无下一项"), 240), "detail": clean_text(next_item.get("detail", ""), 80)},
        "events": events,
        "tasks": tasks,
        "future_events": future_events,
        "news": [{"title": clean_text(item.get("title", item.get("text", "")), 240), "detail": clean_text(item.get("detail", ""), 100)} for item in news],
        "weather": weather,
        "photo_caption": clean_text(source.get("photo_caption", "每日图片占位"), 100),
        "sync_status": clean_text(source.get("sync_status", "演示数据 · 只读"), 120),
    }
    return result, degraded


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("L", (WIDTH, HEIGHT), color=255)
    return image, ImageDraw.Draw(image)


def _header(draw: ImageDraw.ImageDraw, title: str, data: dict[str, Any], page: str) -> None:
    draw.text((64, 64), title, font=get_font(64, bold=True), fill=16)
    date = f"{data['date']}  {data['weekday']}".strip()
    draw.text((66, 152), date, font=get_font(30), fill=70)
    draw.text((WIDTH - 64, 84), f"PW3 · {page}", font=get_font(24), fill=90, anchor="ra")
    draw.line((64, 220, WIDTH - 64, 220), fill=16, width=4)


def _section_title(draw: ImageDraw.ImageDraw, title: str, y: int) -> None:
    draw.text((64, y), title, font=get_font(34, bold=True), fill=16)
    draw.line((64, y + 56, WIDTH - 64, y + 56), fill=70, width=2)


def render_overview(data: dict[str, Any]) -> Image.Image:
    image, draw = _canvas()
    _header(draw, "今日总览", data, "1 / 2")

    draw.rounded_rectangle((64, 260, WIDTH - 64, 490), radius=12, outline=40, width=3)
    draw.text((92, 292), "下一项", font=get_font(28, bold=True), fill=80)
    draw.text((92, 348), data["next_item"]["time"], font=get_font(52, bold=True), fill=16)
    draw_block(draw, data["next_item"]["title"], (278, 342), 650, get_font(42, bold=True), max_lines=2, line_gap=8)
    draw.text((278, 438), data["next_item"]["detail"], font=get_font(26), fill=90)

    _section_title(draw, "今日日程", 540)
    y = 626
    for event in data["events"]:
        draw.text((70, y), event.get("time", "--:--"), font=get_font(30, bold=True), fill=45)
        draw_block(draw, event.get("title", ""), (230, y - 3), 700, get_font(31, bold=True), max_lines=2, line_gap=5)
        draw.text((230, y + 52), event.get("detail", ""), font=get_font(23), fill=100)
        draw.line((64, y + 106, WIDTH - 64, y + 106), fill=170, width=1)
        y += 126

    _section_title(draw, "待办", 1040)
    y = 1120
    for task in data["tasks"][:3]:
        draw.ellipse((72, y + 5, 96, y + 29), outline=45, width=3)
        # Keep the compact task rows clear of the footer; long titles get an explicit ellipsis.
        draw_block(draw, task.get("title", ""), (130, y - 3), 820, get_font(30, bold=True), max_lines=1, line_gap=5)
        draw.text((130, y + 53), task.get("detail", ""), font=get_font(22), fill=100)
        y += 84
    draw.line((64, 1374, WIDTH - 64, 1374), fill=16, width=3)
    draw.text((64, 1398), "固定 fixture · 仅用于本地原型验收", font=get_font(22), fill=90)
    return to_16_gray(image)


def render_agent(data: dict[str, Any]) -> Image.Image:
    image, draw = _canvas()
    _header(draw, "Agent 简报", data, "2 / 2")

    weather = data["weather"]
    draw.rounded_rectangle((64, 260, WIDTH - 64, 452), radius=12, outline=40, width=3)
    draw.text((92, 292), weather["location"], font=get_font(30, bold=True), fill=16)
    draw.text((92, 344), weather["temperature"], font=get_font(56, bold=True), fill=16)
    draw.text((350, 362), weather["condition"], font=get_font(34), fill=60)
    draw.text((WIDTH - 96, 362), weather["high_low"], font=get_font(28), fill=80, anchor="ra")

    _section_title(draw, "今日要闻", 504)
    y = 590
    for index, item in enumerate(data["news"]):
        draw.text((72, y + 2), f"0{index + 1}", font=get_font(26, bold=True), fill=90)
        draw_block(draw, item.get("title", ""), (150, y - 4), 820, get_font(30, bold=True), max_lines=3, line_gap=7)
        draw.line((64, y + 130, WIDTH - 64, y + 130), fill=170, width=1)
        y += 150

    photo_box = (64, 1040, 520, 1320)
    draw.rectangle(photo_box, outline=60, width=3)
    draw.line((64, 1040, 520, 1320), fill=170, width=2)
    draw.line((520, 1040, 64, 1320), fill=170, width=2)
    draw.text((292, 1145), "每日图片", font=get_font(32, bold=True), fill=45, anchor="ma")
    draw.text((292, 1195), "PHOTO PLACEHOLDER", font=get_font(20), fill=100, anchor="ma")
    draw_block(draw, data["photo_caption"], (590, 1065), 390, get_font(29, bold=True), max_lines=4, line_gap=8)
    draw.text((590, 1250), data["sync_status"], font=get_font(22), fill=90)

    draw.line((64, 1374, WIDTH - 64, 1374), fill=16, width=3)
    draw.text((64, 1398), "卡片接口只读 · 后续接 Agent 前保持鉴权与缓存", font=get_font(22), fill=90)
    return to_16_gray(image)


def build_landscape_timeline(data: dict[str, Any]) -> list[dict[str, str]]:
    timeline: list[dict[str, str]] = []
    for item in data.get("events", []):
        timeline.append({
            "time": clean_text(item.get("time", "--:--"), 12),
            "title": clean_text(item.get("title", ""), 240),
            "meta": clean_text(item.get("detail", ""), 100),
            "kind": "日程",
        })
    for item in data.get("tasks", []):
        timeline.append({
            "time": clean_text(item.get("time", "--:--"), 12),
            "title": clean_text(item.get("title", ""), 240),
            "meta": clean_text(item.get("detail", ""), 100),
            "kind": "待办",
        })
    return sorted(timeline, key=lambda item: (item["time"] == "--:--", item["time"]))


def _month_cells(year: int, month: int) -> list[tuple[int, bool, bool]]:
    import calendar

    first_weekday, days_in_month = calendar.monthrange(year, month)
    previous_days = calendar.monthrange(year - 1, 12)[1] if month == 1 else calendar.monthrange(year, month - 1)[1]
    cells: list[tuple[int, bool, bool]] = []
    for index in range(42):
        day_offset = index - first_weekday
        if day_offset < 0:
            cells.append((previous_days + day_offset + 1, False, False))
        elif day_offset >= days_in_month:
            cells.append((day_offset - days_in_month + 1, False, False))
        else:
            cells.append((day_offset + 1, True, day_offset + 1 == 29))
    return cells


def render_landscape(data: dict[str, Any]) -> Image.Image:
    """Render the PW3 horizontal mockup without changing the portrait pages."""
    image = Image.new("L", (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT), color=255)
    draw = ImageDraw.Draw(image)
    left_edge, right_edge = 56, LANDSCAPE_WIDTH - 56
    divider_x = 856
    right_left = divider_x + 42

    # Left column: time dominates the upper visual hierarchy.
    draw.text((left_edge, 46), "09:30", font=get_font(116, bold=True), fill=8)
    draw.text((left_edge + 420, 62), data["weather"]["temperature"], font=get_font(46, bold=True), fill=16)
    draw.text((left_edge + 420, 126), data["weather"]["condition"], font=get_font(29), fill=70)
    draw.text((left_edge + 590, 62), data["date"], font=get_font(30, bold=True), fill=25)
    draw.text((left_edge + 590, 112), data["weekday"], font=get_font(28), fill=80)
    draw.text((left_edge + 420, 188), f"{data['weather']['location']} · 今日天气", font=get_font(22), fill=100)
    draw.line((left_edge, 246, divider_x - 30, 246), fill=16, width=4)

    draw.text((left_edge, 278), "时间线", font=get_font(34, bold=True), fill=16)
    draw.text((divider_x - 30, 288), "按时间排序 · 日程与待办", font=get_font(21), fill=90, anchor="ra")
    timeline = build_landscape_timeline(data)
    row_y = 348
    for item in timeline[:6]:
        if item["kind"] == "待办":
            draw.rectangle((left_edge + 8, row_y + 8, left_edge + 32, row_y + 32), outline=45, width=3)
        else:
            draw.ellipse((left_edge + 12, row_y + 12, left_edge + 28, row_y + 28), fill=45)
        draw.text((left_edge + 58, row_y), item["time"], font=get_font(28, bold=True), fill=35)
        title = truncate_width(draw, item["title"], get_font(29, bold=True), 510)
        draw.text((left_edge + 170, row_y - 2), title, font=get_font(29, bold=True), fill=16)
        meta = " · ".join(filter(None, (item["kind"], item["meta"])))
        draw.text((left_edge + 170, row_y + 42), meta, font=get_font(21), fill=100)
        draw.line((left_edge + 58, row_y + 84, divider_x - 30, row_y + 84), fill=175, width=1)
        row_y += 104

    # Right column: Monday-first full month calendar with previous/next month dates.
    draw.line((divider_x, 46, divider_x, 1016), fill=80, width=3)
    draw.text((right_left, 52), "2026年8月", font=get_font(45, bold=True), fill=16)
    draw.text((right_edge, 72), "月历", font=get_font(24), fill=90, anchor="ra")
    weekday_names = ("一", "二", "三", "四", "五", "六", "日")
    cell_w, cell_h = 68, 66
    calendar_x, calendar_y = right_left, 138
    for column, name in enumerate(weekday_names):
        draw.text((calendar_x + column * cell_w + cell_w // 2, calendar_y), name, font=get_font(22, bold=True), fill=65, anchor="ma")
    for index, (day, in_month, is_today) in enumerate(_month_cells(2026, 8)):
        column, row = index % 7, index // 7
        x = calendar_x + column * cell_w
        y = calendar_y + 42 + row * cell_h
        if is_today:
            draw.rectangle((x + 5, y + 3, x + cell_w - 5, y + cell_h - 5), fill=12)
            draw.text((x + cell_w // 2, y + 18), str(day), font=get_font(24, bold=True), fill=255, anchor="ma")
        else:
            fill = 25 if in_month else 170
            draw.text((x + cell_w // 2, y + 18), str(day), font=get_font(24), fill=fill, anchor="ma")
    calendar_bottom = calendar_y + 42 + 6 * cell_h
    draw.line((right_left, calendar_bottom + 12, right_edge, calendar_bottom + 12), fill=70, width=2)

    draw.text((right_left, calendar_bottom + 42), "本周安排", font=get_font(30, bold=True), fill=16)
    short_y = calendar_bottom + 95
    for item in timeline[:4]:
        draw.text((right_left, short_y), item["time"], font=get_font(22, bold=True), fill=55)
        short_title = truncate_width(draw, item["title"], get_font(23, bold=True), 300)
        draw.text((right_left + 86, short_y), short_title, font=get_font(23, bold=True), fill=16)
        draw.text((right_edge, short_y + 33), item["kind"], font=get_font(19), fill=100, anchor="ra")
        draw.line((right_left, short_y + 58, right_edge, short_y + 58), fill=180, width=1)
        short_y += 72

    draw.line((left_edge, 1018, right_edge, 1018), fill=16, width=3)
    draw.text((left_edge, 1035), "PW3 横放预览 · fixture 数据 · 安装阶段再处理旋转/Framebuffer 方向", font=get_font(20), fill=95)
    return to_16_gray(image)


def _display_landscape_date(value: str) -> str:
    """Use a compact Chinese date below the clock while tolerating fixture fallbacks."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return f"{parsed.year}年{parsed.month}月{parsed.day}日"


def _draw_landscape_control(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    kind: str,
) -> None:
    """Draw a high-contrast, touch-sized status/control tile for the visual mockup."""
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=9, outline=65, width=2)
    cx = (x1 + x2) // 2
    icon_y = y1 + 21
    if kind == "wifi":
        draw.arc((cx - 18, icon_y - 12, cx + 18, icon_y + 18), 215, 325, fill=20, width=3)
        draw.arc((cx - 11, icon_y - 5, cx + 11, icon_y + 13), 215, 325, fill=20, width=3)
        draw.ellipse((cx - 3, icon_y + 12, cx + 3, icon_y + 18), fill=20)
        draw.ellipse((x2 - 15, y1 + 9, x2 - 9, y1 + 15), fill=20)
    elif kind == "battery":
        draw.rectangle((cx - 19, icon_y - 8, cx + 17, icon_y + 9), outline=20, width=2)
        draw.rectangle((cx + 18, icon_y - 3, cx + 22, icon_y + 4), fill=20)
        draw.rectangle((cx - 16, icon_y - 5, cx + 12, icon_y + 6), fill=55)
    elif kind == "brightness":
        draw.ellipse((cx - 7, icon_y - 7, cx + 7, icon_y + 7), outline=20, width=2)
        for dx, dy in ((0, -15), (0, 15), (-15, 0), (15, 0), (-11, -11), (11, 11), (-11, 11), (11, -11)):
            draw.line((cx + dx // 2, icon_y + dy // 2, cx + dx, icon_y + dy), fill=20, width=2)
    else:  # settings: a simple gear-like mark remains legible at low resolution.
        draw.ellipse((cx - 10, icon_y - 10, cx + 10, icon_y + 10), outline=20, width=3)
        draw.ellipse((cx - 3, icon_y - 3, cx + 3, icon_y + 3), fill=20)
        for dx, dy in ((0, -16), (0, 16), (-16, 0), (16, 0)):
            draw.line((cx, icon_y, cx + dx, icon_y + dy), fill=20, width=2)
    draw.text((cx, y2 - 17), label, font=get_font(16, bold=True), fill=45, anchor="mm")


def _landscape_future_events(data: dict[str, Any]) -> list[dict[str, str]]:
    """Return a bounded, display-safe seven-day list from the fixture."""
    items = data.get("future_events")
    if isinstance(items, list):
        normalized = [item for item in items if isinstance(item, dict)]
        if normalized:
            return normalized[:5]
    timeline = build_landscape_timeline(data)
    return [
        {"date": "08月29日", "weekday": "六", "time": item["time"], "title": item["title"], "kind": item["kind"]}
        for item in timeline[:4]
    ]


def render_landscape_v2(data: dict[str, Any]) -> Image.Image:
    """Render the V2 PW3 landscape information wall as an independent mockup."""
    image = Image.new("L", (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT), color=255)
    draw = ImageDraw.Draw(image)
    left_edge, right_edge = 56, LANDSCAPE_WIDTH - 48
    divider_x = 760
    right_left = 800

    # Left header: the clock is the primary signal; date and lunar fixture sit below it.
    draw.text((left_edge, 34), "09:30", font=get_font(114, bold=True), fill=8)
    date_line = f"{_display_landscape_date(data.get('date', ''))}  {data.get('weekday', '')}".strip()
    draw.text((left_edge, 166), date_line, font=get_font(30, bold=True), fill=24)
    lunar = data.get("lunar", "农历信息暂无")
    lunar_note = data.get("lunar_note", "示意")
    draw.text((left_edge, 211), f"{lunar}（{lunar_note}）", font=get_font(23), fill=78)
    weather = data.get("weather", {})
    weather_line = f"{weather.get('location', '未知')}  {weather.get('temperature', '--')}"
    weather_x = left_edge + 444
    draw.text((weather_x, 164), weather_line, font=get_font(34, bold=True), fill=20)
    draw.text((weather_x, 211), f"{weather.get('condition', '暂无天气')}  ·  {weather.get('high_low', '--')}", font=get_font(21), fill=72)
    draw.text((weather_x, 250), "本地天气 · fixture", font=get_font(18), fill=115)
    draw.line((left_edge, 292, divider_x - 32, 292), fill=16, width=4)

    # Left lower panel: one chronological stream, with distinct event/task marks.
    draw.text((left_edge, 322), "时间线", font=get_font(34, bold=True), fill=16)
    draw.text((divider_x - 32, 334), "按时间排序 · 日程与待办", font=get_font(20), fill=90, anchor="ra")
    row_y = 382
    for item in build_landscape_timeline(data)[:6]:
        if item["kind"] == "待办":
            draw.rectangle((left_edge + 9, row_y + 8, left_edge + 31, row_y + 30), outline=45, width=3)
        else:
            draw.ellipse((left_edge + 12, row_y + 11, left_edge + 28, row_y + 27), fill=45)
        draw.text((left_edge + 58, row_y), item["time"], font=get_font(25, bold=True), fill=42)
        title = truncate_width(draw, item["title"], get_font(28, bold=True), 430)
        draw.text((left_edge + 150, row_y - 2), title, font=get_font(28, bold=True), fill=16)
        meta = " · ".join(filter(None, (item["kind"], item["meta"])))
        draw.text((left_edge + 150, row_y + 38), meta, font=get_font(20), fill=100)
        draw.line((left_edge + 58, row_y + 75, divider_x - 32, row_y + 75), fill=175, width=1)
        row_y += 94

    # Right header: month title plus four monochrome touch affordances.
    draw.line((divider_x, 36, divider_x, 1009), fill=80, width=3)
    draw.text((right_left, 45), "2026年8月", font=get_font(39, bold=True), fill=16)
    button_w, button_h, button_gap = 82, 62, 7
    button_x = right_edge - (button_w * 4 + button_gap * 3)
    controls = (("WiFi", "wifi"), ("84%", "battery"), ("亮度", "brightness"), ("设置", "settings"))
    for index, (label, kind) in enumerate(controls):
        x = button_x + index * (button_w + button_gap)
        _draw_landscape_control(draw, (x, 35, x + button_w, 35 + button_h), label, kind)

    # Full Monday-first month grid. Event dots are deliberately inside the day cells.
    weekday_names = ("一", "二", "三", "四", "五", "六", "日")
    cell_w, cell_h = 85, 56
    calendar_x, calendar_y = right_left, 123
    for column, name in enumerate(weekday_names):
        draw.text((calendar_x + column * cell_w + cell_w // 2, calendar_y), name, font=get_font(20, bold=True), fill=65, anchor="ma")
    event_days: set[int] = {29}
    for item in _landscape_future_events(data):
        match = re.search(r"(\d{1,2})月(\d{1,2})日", str(item.get("date", "")))
        if match and int(match.group(1)) == 8:
            event_days.add(int(match.group(2)))
    for index, (day, in_month, is_today) in enumerate(_month_cells(2026, 8)):
        column, row = index % 7, index // 7
        x = calendar_x + column * cell_w
        y = calendar_y + 34 + row * cell_h
        if is_today:
            draw.rounded_rectangle((x + 7, y + 2, x + cell_w - 7, y + cell_h - 4), radius=5, fill=12)
            draw.text((x + cell_w // 2, y + 10), str(day), font=get_font(23, bold=True), fill=255, anchor="ma")
        else:
            fill = 25 if in_month else 175
            draw.text((x + cell_w // 2, y + 10), str(day), font=get_font(23), fill=fill, anchor="ma")
        if in_month and day in event_days:
            dot_fill = 255 if is_today else 45
            draw.ellipse((x + cell_w // 2 - 4, y + 39, x + cell_w // 2 + 4, y + 47), fill=dot_fill)
    calendar_bottom = calendar_y + 34 + 6 * cell_h
    draw.line((right_left, calendar_bottom + 10, right_edge, calendar_bottom + 10), fill=70, width=2)

    # Future seven-day strip: date/weekday, time, title and type remain on one scan line.
    draw.text((right_left, calendar_bottom + 37), "未来7天", font=get_font(30, bold=True), fill=16)
    short_y = calendar_bottom + 86
    for item in _landscape_future_events(data)[:5]:
        date_label = f"{item.get('date', '--月--日')} {item.get('weekday', '-') }"
        draw.text((right_left, short_y), date_label, font=get_font(17, bold=True), fill=60)
        draw.text((right_left + 123, short_y), item.get("time", "--:--"), font=get_font(19, bold=True), fill=42)
        title = truncate_width(draw, item.get("title", "暂无安排"), get_font(21, bold=True), 284)
        draw.text((right_left + 193, short_y - 1), title, font=get_font(21, bold=True), fill=16)
        draw.text((right_edge, short_y + 27), item.get("kind", "日程"), font=get_font(17), fill=100, anchor="ra")
        draw.line((right_left, short_y + 50, right_edge, short_y + 50), fill=180, width=1)
        short_y += 63

    # Compact seasonal/almanac strips stay below the schedule and above the footer.
    solar_term = data.get("solar_term", "节气暂无")
    next_term = data.get("next_solar_term", "下一节气暂无")
    almanac = data.get("almanac", {})
    draw.text((right_left, 895), f"节气：{solar_term}   下一节气：{next_term}", font=get_font(18, bold=True), fill=55)
    draw.text((right_left, 925), f"黄历（示意）：宜 {almanac.get('宜', '暂无')}   忌 {almanac.get('忌', '暂无')}", font=get_font(17), fill=90)

    draw.line((left_edge, 1019, right_edge, 1019), fill=16, width=3)
    draw.text((left_edge, 1037), "PW3 横放预览 V2 · fixture 数据 · 安装阶段再处理旋转/Framebuffer 方向", font=get_font(18), fill=95)
    return to_16_gray(image)


def _draw_landscape_v3_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, kind: str, fill: int) -> None:
    """Draw an unlabeled status/control icon without a button frame."""
    if kind == "brightness":
        draw.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), outline=fill, width=2)
        for dx, dy in ((0, -19), (0, 19), (-19, 0), (19, 0), (-14, -14), (14, 14), (-14, 14), (14, -14)):
            draw.line((cx + dx // 2, cy + dy // 2, cx + dx, cy + dy), fill=fill, width=2)
    elif kind == "settings":
        draw.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), outline=fill, width=3)
        draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=fill)
        for dx, dy in ((0, -19), (0, 19), (-19, 0), (19, 0), (-14, -14), (14, 14), (-14, 14), (14, -14)):
            draw.line((cx, cy, cx + dx, cy + dy), fill=fill, width=2)
    elif kind == "wifi":
        draw.arc((cx - 21, cy - 15, cx + 21, cy + 22), 215, 325, fill=fill, width=3)
        draw.arc((cx - 13, cy - 7, cx + 13, cy + 17), 215, 325, fill=fill, width=3)
        draw.ellipse((cx - 4, cy + 14, cx + 4, cy + 22), fill=fill)
    else:  # battery state
        draw.rectangle((cx - 22, cy - 10, cx + 19, cy + 11), outline=fill, width=2)
        draw.rectangle((cx + 20, cy - 4, cx + 25, cy + 5), fill=fill)
        draw.rectangle((cx - 18, cy - 6, cx + 14, cy + 7), fill=fill)


_LUCIDE_ICON_CACHE: dict[tuple[str, int, int], Image.Image] = {}


def _lucide_icon(name: str, size: int, fill: int = 20) -> Image.Image:
    """Load a vendored Lucide rasterization while preserving the official SVG geometry."""
    key = (name, size, fill)
    if key in _LUCIDE_ICON_CACHE:
        return _LUCIDE_ICON_CACHE[key]
    path = Path(__file__).parent / "assets" / "icons" / "lucide" / "png" / f"{name}.png"
    icon = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    alpha = icon.getchannel("A")
    tinted = Image.new("RGBA", (size, size), (fill, fill, fill, 0))
    tinted.putalpha(alpha)
    _LUCIDE_ICON_CACHE[key] = tinted
    return tinted


def _paste_lucide(draw_image: Image.Image, name: str, xy: tuple[int, int], size: int, fill: int = 20) -> None:
    icon = _lucide_icon(name, size, fill)
    draw_image.paste(icon, xy, icon)


def render_landscape_v3(data: dict[str, Any]) -> Image.Image:
    """Render the V3 PW3 landscape wall with a cleaner, unlabeled status row."""
    image = Image.new("L", (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT), color=255)
    draw = ImageDraw.Draw(image)
    left_edge, right_edge = 56, LANDSCAPE_WIDTH - 48
    divider_x = 760
    right_left = 800

    # Fill the top band: clock, date/lunar lines, and enlarged weather share one baseline system.
    draw.text((left_edge, 34), "09:30", font=get_font(114, bold=True), fill=8)
    date_line = f"{_display_landscape_date(data.get('date', ''))}  {data.get('weekday', '')}".strip()
    draw.text((left_edge, 166), date_line, font=get_font(30, bold=True), fill=24)
    lunar = data.get("lunar", "农历信息暂无")
    lunar_note = data.get("lunar_note", "示意")
    draw.text((left_edge, 211), f"{lunar}（{lunar_note}）", font=get_font(23), fill=78)
    weather = data.get("weather", {})
    weather_x = left_edge + 444
    draw.text((weather_x, 150), f"{weather.get('location', '未知')}  {weather.get('temperature', '--')}", font=get_font(40, bold=True), fill=16)
    draw.text((weather_x, 204), f"{weather.get('condition', '暂无天气')}  ·  {weather.get('high_low', '--')}", font=get_font(23), fill=65)
    draw.line((left_edge, 292, divider_x - 32, 292), fill=16, width=4)

    # Left timeline remains a single chronological stream with event/task marks.
    draw.text((left_edge, 322), "时间线", font=get_font(34, bold=True), fill=16)
    draw.text((divider_x - 32, 334), "按时间排序 · 日程与待办", font=get_font(20), fill=90, anchor="ra")
    row_y = 382
    for item in build_landscape_timeline(data)[:6]:
        if item["kind"] == "待办":
            draw.rectangle((left_edge + 9, row_y + 8, left_edge + 31, row_y + 30), outline=45, width=3)
        else:
            draw.ellipse((left_edge + 12, row_y + 11, left_edge + 28, row_y + 27), fill=45)
        draw.text((left_edge + 58, row_y), item["time"], font=get_font(25, bold=True), fill=42)
        draw.text((left_edge + 150, row_y - 2), truncate_width(draw, item["title"], get_font(28, bold=True), 430), font=get_font(28, bold=True), fill=16)
        draw.text((left_edge + 150, row_y + 38), " · ".join(filter(None, (item["kind"], item["meta"]))), font=get_font(20), fill=100)
        draw.line((left_edge + 58, row_y + 75, divider_x - 32, row_y + 75), fill=175, width=1)
        row_y += 94

    # Right header: month title plus unlabeled icons in the requested order.
    draw.line((divider_x, 36, divider_x, 1009), fill=80, width=3)
    draw.text((right_left, 45), "2026年8月", font=get_font(39, bold=True), fill=16)
    icon_centers = (1115, 1190, 1265, 1340)
    kinds = ("brightness", "settings", "wifi", "battery")
    for index, (cx, kind) in enumerate(zip(icon_centers, kinds)):
        _draw_landscape_v3_icon(draw, cx, 67, kind, 18 if index < 2 else 65)
        if index < 3:
            draw.line((cx + 38, 48, cx + 38, 87), fill=205, width=1)
    draw.line((1100, 101, 1390, 101), fill=220, width=1)

    # Full Monday-first calendar; event dots remain visible inside cells.
    weekday_names = ("一", "二", "三", "四", "五", "六", "日")
    cell_w, cell_h = 85, 56
    calendar_x, calendar_y = right_left, 123
    for column, name in enumerate(weekday_names):
        draw.text((calendar_x + column * cell_w + cell_w // 2, calendar_y), name, font=get_font(20, bold=True), fill=65, anchor="ma")
    event_days: set[int] = {29}
    for item in _landscape_future_events(data):
        match = re.search(r"(\d{1,2})月(\d{1,2})日", str(item.get("date", "")))
        if match and int(match.group(1)) == 8:
            event_days.add(int(match.group(2)))
    for index, (day, in_month, is_today) in enumerate(_month_cells(2026, 8)):
        column, row = index % 7, index // 7
        x = calendar_x + column * cell_w
        y = calendar_y + 34 + row * cell_h
        if is_today:
            draw.rounded_rectangle((x + 7, y + 2, x + cell_w - 7, y + cell_h - 4), radius=5, fill=12)
            draw.text((x + cell_w // 2, y + 10), str(day), font=get_font(23, bold=True), fill=255, anchor="ma")
        else:
            draw.text((x + cell_w // 2, y + 10), str(day), font=get_font(23), fill=25 if in_month else 175, anchor="ma")
        if in_month and day in event_days:
            draw.ellipse((x + cell_w // 2 - 4, y + 39, x + cell_w // 2 + 4, y + 47), fill=255 if is_today else 45)
    calendar_bottom = calendar_y + 34 + 6 * cell_h
    draw.line((right_left, calendar_bottom + 10, right_edge, calendar_bottom + 10), fill=70, width=2)

    # Seasonal/almanac information now precedes the future-seven-day list.
    draw.text((right_left, calendar_bottom + 35), f"节气：{data.get('solar_term', '节气暂无')}   下一节气：{data.get('next_solar_term', '下一节气暂无')}", font=get_font(18, bold=True), fill=55)
    almanac = data.get("almanac", {})
    draw.text((right_left, calendar_bottom + 62), f"黄历（示意）：宜 {almanac.get('宜', '暂无')}   忌 {almanac.get('忌', '暂无')}", font=get_font(17), fill=90)
    draw.text((right_left, calendar_bottom + 101), "未来7天", font=get_font(30, bold=True), fill=16)
    short_y = calendar_bottom + 150
    for item in _landscape_future_events(data)[:5]:
        date_label = f"{item.get('date', '--月--日')} {item.get('weekday', '-') }"
        draw.text((right_left, short_y), date_label, font=get_font(17, bold=True), fill=60)
        draw.text((right_left + 123, short_y), item.get("time", "--:--"), font=get_font(19, bold=True), fill=42)
        draw.text((right_left + 193, short_y - 1), truncate_width(draw, item.get("title", "暂无安排"), get_font(21, bold=True), 284), font=get_font(21, bold=True), fill=16)
        draw.text((right_edge, short_y + 27), item.get("kind", "日程"), font=get_font(17), fill=100, anchor="ra")
        draw.line((right_left, short_y + 50, right_edge, short_y + 50), fill=180, width=1)
        short_y += 63

    # Formal V3 preview deliberately leaves the bottom area blank.
    return to_16_gray(image)


def render_landscape_v4(data: dict[str, Any]) -> Image.Image:
    """Render V4 using vendored Lucide SVG rasterizations for all iconography."""
    image = Image.new("L", (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT), color=255)
    draw = ImageDraw.Draw(image)
    left_edge, right_edge, divider_x, right_left = 56, LANDSCAPE_WIDTH - 48, 760, 800

    # Top band: a condition-selected Lucide weather icon fills the former blank area.
    draw.text((left_edge, 34), "09:30", font=get_font(114, bold=True), fill=8)
    draw.text((left_edge, 166), f"{_display_landscape_date(data.get('date', ''))}  {data.get('weekday', '')}".strip(), font=get_font(30, bold=True), fill=24)
    draw.text((left_edge, 211), f"{data.get('lunar', '农历信息暂无')}（{data.get('lunar_note', '示意')}）", font=get_font(23), fill=78)
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"
    weather_x = left_edge + 444
    _paste_lucide(image, icon_name, (weather_x, 54), 78, 35)
    draw.text((weather_x, 150), f"{weather.get('location', '未知')}  {weather.get('temperature', '--')}", font=get_font(36, bold=True), fill=16)
    draw.text((weather_x, 203), f"{condition or '暂无天气'}  ·  {weather.get('high_low', '--')}", font=get_font(21), fill=65)
    draw.line((left_edge, 292, divider_x - 32, 292), fill=16, width=4)

    # Left timeline remains the merged chronological event/task stream.
    draw.text((left_edge, 322), "时间线", font=get_font(34, bold=True), fill=16)
    draw.text((divider_x - 32, 334), "按时间排序 · 日程与待办", font=get_font(20), fill=90, anchor="ra")
    row_y = 382
    for item in build_landscape_timeline(data)[:6]:
        if item["kind"] == "待办":
            draw.rectangle((left_edge + 9, row_y + 8, left_edge + 31, row_y + 30), outline=45, width=3)
        else:
            draw.ellipse((left_edge + 12, row_y + 11, left_edge + 28, row_y + 27), fill=45)
        draw.text((left_edge + 58, row_y), item["time"], font=get_font(25, bold=True), fill=42)
        title_font = get_font(28, bold=True)
        draw.text((left_edge + 150, row_y - 2), truncate_width(draw, item["title"], title_font, 430), font=title_font, fill=16)
        draw.text((left_edge + 150, row_y + 38), " · ".join(filter(None, (item["kind"], item["meta"]))), font=get_font(20), fill=100)
        draw.line((left_edge + 58, row_y + 75, divider_x - 32, row_y + 75), fill=175, width=1)
        row_y += 94

    # Right header keeps only the clickable settings icon.
    draw.line((divider_x, 36, divider_x, 981), fill=80, width=3)
    draw.text((right_left, 45), "2026年8月", font=get_font(39, bold=True), fill=16)
    _paste_lucide(image, "settings", (1322, 42), 56, 18)
    draw.line((1308, 101, 1390, 101), fill=220, width=1)

    # Calendar and event dots.
    weekday_names = ("一", "二", "三", "四", "五", "六", "日")
    cell_w, cell_h, calendar_x, calendar_y = 85, 56, right_left, 123
    for column, name in enumerate(weekday_names):
        draw.text((calendar_x + column * cell_w + cell_w // 2, calendar_y), name, font=get_font(20, bold=True), fill=65, anchor="ma")
    event_days: set[int] = {29}
    for item in _landscape_future_events(data):
        match = re.search(r"(\d{1,2})月(\d{1,2})日", str(item.get("date", "")))
        if match and int(match.group(1)) == 8:
            event_days.add(int(match.group(2)))
    for index, (day, in_month, is_today) in enumerate(_month_cells(2026, 8)):
        column, row = index % 7, index // 7
        x, y = calendar_x + column * cell_w, calendar_y + 34 + row * cell_h
        if is_today:
            draw.rounded_rectangle((x + 7, y + 2, x + cell_w - 7, y + cell_h - 4), radius=5, fill=12)
            draw.text((x + cell_w // 2, y + 10), str(day), font=get_font(23, bold=True), fill=255, anchor="ma")
        else:
            draw.text((x + cell_w // 2, y + 10), str(day), font=get_font(23), fill=25 if in_month else 175, anchor="ma")
        if in_month and day in event_days:
            draw.ellipse((x + cell_w // 2 - 4, y + 39, x + cell_w // 2 + 4, y + 47), fill=255 if is_today else 45)
    calendar_bottom = calendar_y + 34 + 6 * cell_h
    draw.line((right_left, calendar_bottom + 10, right_edge, calendar_bottom + 10), fill=70, width=2)

    # Seasonal/almanac lines precede the future-seven-day list.
    draw.text((right_left, calendar_bottom + 35), f"节气：{data.get('solar_term', '节气暂无')}   下一节气：{data.get('next_solar_term', '下一节气暂无')}", font=get_font(18, bold=True), fill=55)
    almanac = data.get("almanac", {})
    draw.text((right_left, calendar_bottom + 62), f"黄历（示意）：宜 {almanac.get('宜', '暂无')}   忌 {almanac.get('忌', '暂无')}", font=get_font(17), fill=90)
    draw.text((right_left, calendar_bottom + 101), "未来7天", font=get_font(30, bold=True), fill=16)
    short_y = calendar_bottom + 150
    for item in _landscape_future_events(data)[:5]:
        draw.text((right_left, short_y), f"{item.get('date', '--月--日')} {item.get('weekday', '-')}", font=get_font(17, bold=True), fill=60)
        draw.text((right_left + 123, short_y), item.get("time", "--:--"), font=get_font(19, bold=True), fill=42)
        title_font = get_font(21, bold=True)
        draw.text((right_left + 193, short_y - 1), truncate_width(draw, item.get("title", "暂无安排"), title_font, 284), font=title_font, fill=16)
        draw.text((right_edge, short_y + 27), item.get("kind", "日程"), font=get_font(17), fill=100, anchor="ra")
        draw.line((right_left, short_y + 50, right_edge, short_y + 50), fill=180, width=1)
        short_y += 63

    # Bottom separator and icon-only control/status strip; no footer text.
    draw.line((left_edge, 981, right_edge, 981), fill=70, width=2)
    _paste_lucide(image, "sun", (left_edge + 7, 996), 56, 18)
    _paste_lucide(image, "wifi", (right_edge - 125, 996), 48, 65)
    _paste_lucide(image, "battery", (right_edge - 53, 996), 48, 65)
    draw.text((right_edge - 3, 994), "84%", font=get_font(14), fill=90, anchor="ra")
    return to_16_gray(image)


def render_landscape_v5(data: dict[str, Any]) -> Image.Image:
    """Polish V4 spacing and controls while preserving the earlier preview files."""
    image = render_landscape_v4(data).convert("L")
    draw = ImageDraw.Draw(image)
    left_edge, right_edge = 56, LANDSCAPE_WIDTH - 48
    divider_x, right_left = 760, 800

    # Recompose the weather block on one compact baseline: icon left, text right.
    draw.rectangle((470, 38, divider_x - 36, 285), fill=255)
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"
    _paste_lucide(image, icon_name, (486, 153), 54, 35)
    draw.text((552, 151), f"{weather.get('location', '未知')}  {weather.get('temperature', '--')}", font=get_font(31, bold=True), fill=16)
    draw.text((552, 199), f"{condition or '暂无天气'}  ·  {weather.get('high_low', '--')}", font=get_font(20), fill=65)

    # Tighten the lunar-to-rule gap and keep the lunar line free of a parenthetical note.
    draw.rectangle((50, 204, 500, 242), fill=255)
    draw.text((left_edge, 211), str(data.get("lunar", "农历信息暂无")), font=get_font(23), fill=78)
    draw.rectangle((50, 284, divider_x - 16, 301), fill=255)
    draw.line((left_edge, 270, divider_x - 32, 270), fill=16, width=4)
    _paste_lucide(image, icon_name, (486, 153), 54, 35)

    # Remove the header rule and make the settings glyph smaller and finer.
    draw.rectangle((1290, 28, 1405, 110), fill=255)
    _paste_lucide(image, "settings", (1330, 48), 42, 18)

    # Shorten the bottom divider to the content margins and redraw smaller icons.
    draw.rectangle((40, 968, 1410, 1071), fill=255)
    draw.line((64, 980, 1384, 980), fill=70, width=2)
    _paste_lucide(image, "sun", (72, 997), 40, 18)
    _paste_lucide(image, "wifi", (1280, 997), 38, 65)
    _paste_lucide(image, "battery", (1342, 997), 38, 65)
    return to_16_gray(image)


def render_landscape_v6(data: dict[str, Any]) -> Image.Image:
    """Align the weather block to the three-line date stack and use a battery glyph state."""
    image = render_landscape_v5(data).convert("L")
    draw = ImageDraw.Draw(image)
    left_edge, right_edge, divider_x = 56, LANDSCAPE_WIDTH - 48, 760

    # The weather pictogram occupies the clock-height column; its two text rows match date/lunar baselines.
    draw.rectangle((430, 35, divider_x - 16, 266), fill=255)
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"
    _paste_lucide(image, icon_name, (460, 43), 100, 35)
    draw.text((570, 166), f"{weather.get('location', '未知')}  {weather.get('temperature', '--')}", font=get_font(30, bold=True), fill=16)
    draw.text((570, 211), f"{condition or '暂无天气'}  ·  {weather.get('high_low', '--')}", font=get_font(20), fill=65)

    # Repaint the footer separator cleanly and use the Lucide medium-battery state without a number.
    draw.rectangle((40, 968, 1410, 1071), fill=255)
    draw.line((64, 980, 1384, 980), fill=70, width=2)
    _paste_lucide(image, "sun", (72, 997), 40, 18)
    _paste_lucide(image, "wifi", (1280, 997), 38, 65)
    _paste_lucide(image, "battery-medium", (1342, 997), 38, 65)
    return to_16_gray(image)


def render_landscape_v7(data: dict[str, Any]) -> Image.Image:
    """Refine the V6 weather block into four aligned, compact information rows."""
    image = render_landscape_v6(data).convert("L")
    draw = ImageDraw.Draw(image)
    divider_x = 760
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"

    # Keep the icon at clock height; right-align all weather text to one clean edge.
    draw.rectangle((430, 35, divider_x - 16, 267), fill=255)
    _paste_lucide(image, icon_name, (458, 43), 100, 35)
    text_right = divider_x - 32
    draw.text((text_right, 126), str(weather.get("location", "未知")), font=get_font(22, bold=True), fill=16, anchor="ra")
    draw.text((text_right, 159), str(weather.get("temperature", "--")), font=get_font(33, bold=True), fill=16, anchor="ra")
    draw.text((text_right, 204), f"{condition or '暂无天气'}  ·  {weather.get('high_low', '--')}", font=get_font(18), fill=55, anchor="ra")
    draw.text((text_right, 237), "降雨概率 30%  ·  紫外线 低  ·  风速 3级", font=get_font(14), fill=85, anchor="ra")
    return to_16_gray(image)


def render_landscape_v8(data: dict[str, Any]) -> Image.Image:
    """Place the weather icon and city/temperature on one primary row."""
    image = render_landscape_v7(data).convert("L")
    draw = ImageDraw.Draw(image)
    divider_x = 760
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"

    draw.rectangle((430, 35, divider_x - 16, 267), fill=255)
    # Primary weather row: the large icon and Shanghai/current temperature share one horizontal band.
    _paste_lucide(image, icon_name, (458, 43), 100, 35)
    text_right = divider_x - 32
    draw.text((text_right, 86), f"{weather.get('location', '未知')}  {weather.get('temperature', '--')}", font=get_font(30, bold=True), fill=16, anchor="ra")
    # Secondary rows align exactly with the date and lunar baselines on the left.
    draw.text((text_right, 166), f"{condition or '暂无天气'}  ·  {weather.get('high_low', '--')}", font=get_font(18), fill=55, anchor="ra")
    draw.text((text_right, 211), "降雨概率 30%  ·  紫外线 低  ·  风速 3级", font=get_font(14), fill=85, anchor="ra")
    return to_16_gray(image)


def render_landscape_v9(data: dict[str, Any]) -> Image.Image:
    """Align weather as icon+stacked city/temperature, then date/lunar-sized rows."""
    image = render_landscape_v8(data).convert("L")
    draw = ImageDraw.Draw(image)
    divider_x = 760
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"

    draw.rectangle((430, 35, divider_x - 16, 267), fill=255)
    # The first weather row occupies the same height band as the clock.
    _paste_lucide(image, icon_name, (458, 43), 100, 35)
    text_right = divider_x - 32
    draw.text((text_right, 70), str(weather.get("location", "未知")), font=get_font(20, bold=True), fill=35, anchor="ra")
    draw.text((text_right, 126), str(weather.get("temperature", "--")), font=get_font(38, bold=True), fill=16, anchor="ra")
    # Rows two and three line up with the date and lunar baselines on the left.
    draw.text((text_right, 166), f"{condition or '暂无天气'}  ·  {weather.get('high_low', '--')}", font=get_font(22), fill=55, anchor="ra")
    draw.text((text_right, 211), "降雨概率 30%  ·  紫外线 低  ·  风速 3级", font=get_font(14), fill=85, anchor="ra")
    return to_16_gray(image)


def render_landscape_v10(data: dict[str, Any]) -> Image.Image:
    """Match weather row sizes to date/lunar text and tighten the footer controls."""
    image = render_landscape_v9(data).convert("L")
    draw = ImageDraw.Draw(image)
    divider_x = 760
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"

    draw.rectangle((430, 35, divider_x - 16, 267), fill=255)
    # Keep the icon and stacked city/temperature inside the clock's vertical band.
    _paste_lucide(image, icon_name, (458, 43), 96, 35)
    text_right = divider_x - 32
    draw.text((text_right, 68), str(weather.get("location", "未知")), font=get_font(18, bold=True), fill=35, anchor="ra")
    draw.text((text_right, 126), str(weather.get("temperature", "--")), font=get_font(32, bold=True), fill=16, anchor="ra")
    # Exact matching sizes: date uses 30px and lunar uses 23px in the base layout.
    draw.text((text_right, 166), f"{condition or '暂无天气'} · {weather.get('high_low', '--')}", font=get_font(30), fill=55, anchor="ra")
    draw.text((text_right, 211), "雨30% · UV低 · 风3级", font=get_font(23), fill=85, anchor="ra")

    # Compress the footer whitespace and use smaller status glyphs.
    draw.rectangle((40, 970, 1400, 1045), fill=255)
    draw.line((64, 1014, 1384, 1014), fill=70, width=2)
    _paste_lucide(image, "sun", (72, 1021), 30, 18)
    _paste_lucide(image, "wifi", (1288, 1021), 30, 65)
    _paste_lucide(image, "battery-medium", (1344, 1021), 30, 65)
    return to_16_gray(image)


def render_landscape_v11(data: dict[str, Any]) -> Image.Image:
    """Scale the temperature to two-thirds of the clock while closing the city gap."""
    image = render_landscape_v10(data).convert("L")
    draw = ImageDraw.Draw(image)
    divider_x = 760
    weather = data.get("weather", {})
    condition = str(weather.get("condition", ""))
    icon_name = "cloud-rain" if "雨" in condition else "sun" if "晴" in condition else "cloud-sun"
    draw.rectangle((430, 35, divider_x - 16, 267), fill=255)
    _paste_lucide(image, icon_name, (458, 47), 88, 35)
    text_right = divider_x - 32
    # City label matches the solar-term text; temperature is ~2/3 of the clock size.
    draw.text((text_right, 50), str(weather.get("location", "未知")), font=get_font(18, bold=True), fill=35, anchor="ra")
    temperature = str(weather.get("temperature", "--")).replace("°C", "°")
    draw.text((text_right, 68), temperature, font=get_font(76, bold=True), fill=16, anchor="ra")
    draw.text((text_right, 166), f"{condition or '暂无天气'} · {weather.get('high_low', '--')}", font=get_font(30), fill=55, anchor="ra")
    draw.text((text_right, 211), "雨30% · UV低 · 风3级", font=get_font(23), fill=85, anchor="ra")
    return to_16_gray(image)


def render_landscape_v12(data: dict[str, Any]) -> Image.Image:
    """Enlarge the right information wall for native-size PW3 viewing."""
    image = render_landscape_v11(data).convert("L")
    draw = ImageDraw.Draw(image)
    right_left, right_edge = 800, LANDSCAPE_WIDTH - 48
    draw.rectangle((780, 35, right_edge, 970), fill=255)
    draw.text((right_left, 45), "2026年8月", font=get_font(45, bold=True), fill=16)
    _paste_lucide(image, "settings", (1328, 48), 38, 18)

    weekday_names = ("一", "二", "三", "四", "五", "六", "日")
    cell_w, cell_h, calendar_x, calendar_y = 85, 56, right_left, 123
    for column, name in enumerate(weekday_names):
        draw.text((calendar_x + column * cell_w + cell_w // 2, calendar_y), name, font=get_font(24, bold=True), fill=65, anchor="ma")
    event_days: set[int] = {29}
    for item in _landscape_future_events(data):
        match = re.search(r"(\d{1,2})月(\d{1,2})日", str(item.get("date", "")))
        if match and int(match.group(1)) == 8:
            event_days.add(int(match.group(2)))
    for index, (day, in_month, is_today) in enumerate(_month_cells(2026, 8)):
        column, row = index % 7, index // 7
        x, y = calendar_x + column * cell_w, calendar_y + 34 + row * cell_h
        if is_today:
            draw.rounded_rectangle((x + 5, y + 1, x + cell_w - 5, y + cell_h - 3), radius=5, fill=12)
            draw.text((x + cell_w // 2, y + 8), str(day), font=get_font(28, bold=True), fill=255, anchor="ma")
        else:
            draw.text((x + cell_w // 2, y + 8), str(day), font=get_font(28), fill=25 if in_month else 175, anchor="ma")
        if in_month and day in event_days:
            draw.ellipse((x + cell_w // 2 - 4, y + 42, x + cell_w // 2 + 4, y + 50), fill=255 if is_today else 45)

    calendar_bottom = calendar_y + 34 + 6 * cell_h
    draw.line((right_left, calendar_bottom + 10, right_edge, calendar_bottom + 10), fill=70, width=2)
    draw.text((right_left, calendar_bottom + 35), f"节气：{data.get('solar_term', '节气暂无')}   下一节气：{data.get('next_solar_term', '下一节气暂无')}", font=get_font(22, bold=True), fill=55)
    almanac = data.get("almanac", {})
    draw.text((right_left, calendar_bottom + 65), f"黄历（示意）：宜 {almanac.get('宜', '暂无')}   忌 {almanac.get('忌', '暂无')}", font=get_font(21), fill=90)
    draw.text((right_left, calendar_bottom + 106), "下一周的日程", font=get_font(34, bold=True), fill=16)
    short_y = calendar_bottom + 153
    for item in _landscape_future_events(data)[:5]:
        draw.text((right_left, short_y), f"{item.get('date', '--月--日')} {item.get('weekday', '-')}", font=get_font(20, bold=True), fill=60)
        draw.text((right_left + 123, short_y), item.get("time", "--:--"), font=get_font(22, bold=True), fill=42)
        title_font = get_font(28, bold=True)
        draw.text((right_left + 193, short_y - 2), truncate_width(draw, item.get("title", "暂无安排"), title_font, 284), font=title_font, fill=16)
        draw.text((right_edge, short_y + 31), item.get("kind", "日程"), font=get_font(20), fill=100, anchor="ra")
        draw.line((right_left, short_y + 58, right_edge, short_y + 58), fill=180, width=1)
        short_y += 67
    return to_16_gray(image)


def render_landscape_v13(data: dict[str, Any]) -> Image.Image:
    """Clarify the timeline label and separate the right-column sections."""
    image = render_landscape_v12(data).convert("L")
    draw = ImageDraw.Draw(image)
    right_left, right_edge = 800, LANDSCAPE_WIDTH - 48
    # Replace only the left timeline heading.
    draw.rectangle((50, 315, 360, 365), fill=255)
    draw.text((56, 322), "待办事项 & 日程", font=get_font(34, bold=True), fill=16)

    # Repaint the seasonal block with schedule-sized type and a clear section break.
    calendar_bottom = 123 + 34 + 6 * 56
    draw.rectangle((780, calendar_bottom + 20, right_edge, 970), fill=255)
    draw.text((right_left, calendar_bottom + 35), f"节气：{data.get('solar_term', '节气暂无')}   下一节气：{data.get('next_solar_term', '下一节气暂无')}", font=get_font(24, bold=True), fill=55)
    almanac = data.get("almanac", {})
    draw.text((right_left, calendar_bottom + 70), f"黄历（示意）：宜 {almanac.get('宜', '暂无')}   忌 {almanac.get('忌', '暂无')}", font=get_font(23), fill=90)
    draw.line((right_left, calendar_bottom + 101, right_edge, calendar_bottom + 101), fill=170, width=1)
    draw.text((right_left, calendar_bottom + 125), "下一周的日程", font=get_font(34, bold=True), fill=16)
    short_y = calendar_bottom + 178
    for item in _landscape_future_events(data)[:5]:
        draw.text((right_left, short_y), f"{item.get('date', '--月--日')} {item.get('weekday', '-')}", font=get_font(20, bold=True), fill=60)
        draw.text((right_left + 123, short_y), item.get("time", "--:--"), font=get_font(22, bold=True), fill=42)
        title_font = get_font(28, bold=True)
        draw.text((right_left + 193, short_y - 2), truncate_width(draw, item.get("title", "暂无安排"), title_font, 284), font=title_font, fill=16)
        draw.text((right_edge, short_y + 31), item.get("kind", "日程"), font=get_font(20), fill=100, anchor="ra")
        draw.line((right_left, short_y + 58, right_edge, short_y + 58), fill=180, width=1)
        short_y += 67
    return to_16_gray(image)


def to_16_gray(image: Image.Image) -> Image.Image:
    """Return a palette PNG image with exactly the 16 grayscale entries."""
    gray = image.convert("L")
    lut = [min(range(GRAY_LEVELS), key=lambda index: abs(PALETTE[index] - value)) for value in range(256)]
    indexed = gray.point(lut, mode="P")
    palette: list[int] = []
    for value in PALETTE:
        palette.extend((value, value, value))
    palette.extend([0] * (768 - len(palette)))
    indexed.putpalette(palette)
    return indexed


class DashboardState:
    def __init__(self, assets_dir: str | Path, fixture_path: str | Path | None = None) -> None:
        self.assets_dir = Path(assets_dir)
        self.fixture_path = Path(fixture_path) if fixture_path else None
        self.data, self.degraded = prepare_data(load_fixture(self.fixture_path))
        self.manifest = self._build_assets()
        self.landscape_manifest = self._build_landscape_manifest()

    def _build_assets(self) -> dict[str, Any]:
        pages_dir = self.assets_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        page_specs = (
            ("today-overview", render_overview(self.data)),
            ("agent-brief", render_agent(self.data)),
        )
        pages: list[dict[str, Any]] = []
        for page_id, image in page_specs:
            target = pages_dir / f"{page_id}.png"
            image.save(target, format="PNG", bits=4, optimize=True)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            pages.append({
                "id": page_id,
                "path": f"/pages/{page_id}.png",
                "format": "png",
                "width": WIDTH,
                "height": HEIGHT,
                "grayscale_levels": GRAY_LEVELS,
                "sha256": digest,
                "hold_seconds": 45,
            })
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=6)
        return {
            "manifest_version": "1",
            "app_version": VERSION,
            "device": {"model": "kindle-paperwhite-3", "orientation": "portrait", "width": WIDTH, "height": HEIGHT},
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "valid_until": expires.isoformat().replace("+00:00", "Z"),
            "pages": pages,
            "fallback": {
                "active": bool(self.degraded),
                "reasons": self.degraded,
                "empty_payload": "serve-safe-placeholder",
                "long_text": "wrap-then-ellipsis",
                "last_good": "keep-device-cache",
            },
        }

    def _build_landscape_manifest(self) -> dict[str, Any]:
        pages_dir = self.assets_dir / "pages"
        target = pages_dir / "landscape-mockup-v13.png"
        source = Path(__file__).parent / "public" / "pages" / "landscape-mockup-v13.png"
        if not target.exists() and source.exists():
            shutil.copyfile(source, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        now = datetime.now(timezone.utc)
        return {
            "manifest_version": "1",
            "app_version": VERSION,
            "layout_version": "v13",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "valid_until": (now + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
            "ttl_seconds": 21600,
            "device": {"model": "kindle-paperwhite-3", "orientation": "landscape", "width": LANDSCAPE_WIDTH, "height": LANDSCAPE_HEIGHT},
            "page": {"id": "landscape-mockup-v13", "path": "/pages/landscape-mockup-v13.png", "format": "png", "width": LANDSCAPE_WIDTH, "height": LANDSCAPE_HEIGHT, "grayscale_levels": GRAY_LEVELS, "sha256": digest, "hold_seconds": 45},
            "fixture_summary": {
                "date": self.data.get("date"), "weekday": self.data.get("weekday"),
                "events": len(self.data.get("events", [])), "tasks": len(self.data.get("tasks", [])),
                "future_events": len(self.data.get("future_events", [])), "news": len(self.data.get("news", [])),
                "weather_location": self.data.get("weather", {}).get("location"),
                "sync_status": self.data.get("sync_status"), "degraded": bool(self.degraded),
            },
            "fallback": {"active": bool(self.degraded), "reasons": self.degraded, "empty_payload": "serve-safe-placeholder", "long_text": "wrap-then-ellipsis", "last_good": "keep-device-cache"},
        }


def make_handler(state: DashboardState):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"KindleAgentDashboard/{VERSION}"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            path = urlparse(self.path).path
            if path == "/health":
                self._json({"status": "ok", "version": VERSION, "device": state.manifest["device"]})
                return
            if path in ("/manifest.json", "/api/manifest"):
                self._json(state.manifest)
                return
            if path in ("/landscape/manifest.json", "/api/landscape/manifest"):
                self._json(state.landscape_manifest)
                return
            if path == "/":
                body = (
                    "<!doctype html><meta charset='utf-8'><title>Kindle Agent Demo</title>"
                    "<h1>Kindle Agent 看板原型</h1><p>只读 fixture 演示，不含真实账号。</p>"
                    "<ul><li><a href='/manifest.json'>manifest.json</a></li>"
                    "<li><a href='/pages/today-overview.png'>今日总览</a></li>"
                    "<li><a href='/pages/agent-brief.png'>Agent 简报</a></li></ul>"
                ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path.startswith("/pages/") and path.endswith(".png"):
                target = state.assets_dir / path.removeprefix("/")
                if target.is_file() and target.parent == state.assets_dir / "pages":
                    body = target.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "public, max-age=300")
                    self.end_headers()
                    self.wfile.write(body)
                    return
            self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    return Handler


def serve(host: str, port: int, assets_dir: str, fixture_path: str | None = None) -> None:
    state = DashboardState(assets_dir, fixture_path)
    server = ThreadingHTTPServer((host, port), make_handler(state))
    print(json.dumps({"url": f"http://{host}:{port}", "manifest": state.manifest}, ensure_ascii=False))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local PW3 dashboard demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18500)
    parser.add_argument("--assets", default="public")
    parser.add_argument("--fixture", default=None)
    args = parser.parse_args()
    serve(args.host, args.port, args.assets, args.fixture)


if __name__ == "__main__":
    main()
