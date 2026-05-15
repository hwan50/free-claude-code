"""Convert insight markdown notes to slides-config.json for generate-slides.js.

Reads an insight markdown file whose YAML frontmatter describes one slide
(hook, context, theme_color, key_metric_*, caption, source) and emits a
layered JSON config that the Node Canvas renderer can consume.

Usage:
    uv run python tools/insight_to_slides.py <insight.md> [-o output.json]
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Canvas:
    width: int = 1080
    height: int = 1440


@dataclass(frozen=True, slots=True)
class Insight:
    hook: str
    context: str = ""
    theme_color: str = "#ff6b35"
    bg_color: str = "#1a1a1a"
    key_metric_label: str = ""
    key_metric_value: str = ""
    caption: str = ""
    source: str = ""


def strip_inline_comment(value: str) -> str:
    """Trim a trailing `# comment`, leaving `#` inside quoted strings alone."""
    in_quote: str | None = None
    for i, ch in enumerate(value):
        if in_quote is None:
            if ch in ('"', "'"):
                in_quote = ch
            elif ch == "#":
                return value[:i].rstrip()
        elif ch == in_quote:
            in_quote = None
    return value


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse a minimal YAML frontmatter block (single-line scalar values only).

    Multi-line scalars and nested structures are intentionally unsupported —
    the insight schema for this pipeline is flat strings.
    """
    text = content.lstrip("﻿").lstrip()
    if not text.startswith("---"):
        raise ValueError(
            "Insight markdown must start with a `---` frontmatter delimiter"
        )
    rest = text[3:]
    end = rest.find("\n---")
    if end == -1:
        raise ValueError("Frontmatter is not closed with `---` on its own line")
    fm_text = rest[:end]
    fields: dict[str, str] = {}
    for raw in fm_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = strip_inline_comment(value.strip())
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def insight_from_frontmatter(fields: dict[str, str]) -> Insight:
    hook = fields.get("hook", "").strip()
    if not hook:
        raise ValueError("Frontmatter must contain a non-empty `hook` field")
    return Insight(
        hook=hook,
        context=fields.get("context", ""),
        theme_color=fields.get("theme_color", "#ff6b35"),
        bg_color=fields.get("bg_color", "#1a1a1a"),
        key_metric_label=fields.get("key_metric_label", ""),
        key_metric_value=fields.get("key_metric_value", ""),
        caption=fields.get("caption", ""),
        source=fields.get("source", ""),
    )


def hook_font_size(hook: str) -> int:
    """Step the hook font down as it gets longer, per the project spec."""
    n = len(hook)
    if n <= 20:
        return 86
    if n <= 30:
        return 72
    return 64


def metric_font_size(value: str) -> int:
    """Scale key_metric_value between 96 (short numeric) and 44 (long list)."""
    n = len(value)
    if n <= 6:
        return 96
    if n <= 10:
        return 80
    if n <= 16:
        return 64
    if n <= 22:
        return 56
    return 44


def _parse_hex(color: str) -> tuple[int, int, int]:
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _tint_toward(theme: str, bg: str, ratio: float) -> str:
    """Mix `theme` toward `bg` by `ratio` (0=theme, 1=bg). Returns #rrggbb."""
    t = _parse_hex(theme)
    b = _parse_hex(bg)
    out = tuple(int(t[i] * (1 - ratio) + b[i] * ratio) for i in range(3))
    return f"#{out[0]:02x}{out[1]:02x}{out[2]:02x}"


def _estimate_wrapped_lines(text: str, font_size: int, max_width: int) -> int:
    """Conservative line-count estimate. CJK ~= 1.0 em wide, ASCII ~= 0.55 em."""
    if not text:
        return 0
    em = font_size
    used = 0.0
    lines = 1
    for ch in text:
        code = ord(ch)
        is_cjk = 0x3000 <= code <= 0x9FFF or 0xFF00 <= code <= 0xFFEF
        w = em if is_cjk else em * 0.55
        if used + w > max_width:
            lines += 1
            used = w
        else:
            used += w
    return lines


def build_slides_config(insight: Insight, canvas: Canvas) -> dict[str, Any]:
    w, h = canvas.width, canvas.height
    text_x = 80
    text_max_width = w - text_x * 2
    card_x = 60
    card_w = w - card_x * 2

    hook_size = hook_font_size(insight.hook)
    metric_size = metric_font_size(insight.key_metric_value)

    context_y = round(h * 0.10)
    hook_y = round(h * 0.17)
    hook_lines = _estimate_wrapped_lines(insight.hook, hook_size, text_max_width)
    hook_bottom_y = hook_y + int(hook_size * 1.3 * hook_lines)
    accent_y = hook_bottom_y + 36

    metric_lines = _estimate_wrapped_lines(
        insight.key_metric_value, metric_size, text_max_width - 32
    )
    metric_value_h = int(metric_size * 1.15 * metric_lines)

    label_block = (36 + 28) if insight.key_metric_label else 0
    value_block = metric_value_h
    caption_block = (32 + 28) if insight.caption else 0
    card_pad = 56
    card_h = card_pad * 2 + label_block + value_block + caption_block
    card_y = h - 200 - card_h  # leaves room for the source row below

    inner_y = card_y + card_pad
    label_y = inner_y
    value_y = label_y + (label_block if insight.key_metric_label else 0)
    caption_y = value_y + value_block + 28

    source_y = h - 70
    card_color = _tint_toward(insight.theme_color, insight.bg_color, 0.88)

    layers: list[dict[str, Any]] = [
        # Full-height left color bar (kept for branding continuity)
        {
            "type": "rect",
            "x": 0,
            "y": 0,
            "width": 6,
            "height": h,
            "color": insight.theme_color,
        },
        # Short top horizontal accent — gives a magazine-cover feel
        {
            "type": "rect",
            "x": 0,
            "y": 0,
            "width": 220,
            "height": 8,
            "color": insight.theme_color,
        },
    ]

    if insight.context:
        dot = 18
        layers.append(
            {
                "type": "rect",
                "x": text_x,
                "y": context_y + 14,
                "width": dot,
                "height": dot,
                "color": insight.theme_color,
            }
        )
        layers.append(
            {
                "type": "text",
                "x": text_x + dot + 18,
                "y": context_y,
                "text": insight.context,
                "fontSize": 36,
                "color": "#ccc",
                "maxWidth": text_max_width - dot - 18,
            }
        )

    layers.append(
        {
            "type": "text",
            "x": text_x,
            "y": hook_y,
            "text": insight.hook,
            "fontSize": hook_size,
            "color": "#fff",
            "weight": "bold",
            "lineHeight": 1.3,
            "maxWidth": text_max_width,
            "wrap": True,
        }
    )

    # Short accent rule under the hook to close off the hero zone
    layers.append(
        {
            "type": "rect",
            "x": text_x,
            "y": accent_y,
            "width": 96,
            "height": 4,
            "color": insight.theme_color,
        }
    )

    # Metric card background + left stripe
    layers.append(
        {
            "type": "rect",
            "x": card_x,
            "y": card_y,
            "width": card_w,
            "height": card_h,
            "color": card_color,
        }
    )
    layers.append(
        {
            "type": "rect",
            "x": card_x,
            "y": card_y,
            "width": 4,
            "height": card_h,
            "color": insight.theme_color,
        }
    )

    if insight.key_metric_label:
        layers.append(
            {
                "type": "text",
                "x": text_x,
                "y": label_y,
                "text": insight.key_metric_label,
                "fontSize": 36,
                "color": "#bbb",
                "maxWidth": text_max_width,
            }
        )

    if insight.key_metric_value:
        layers.append(
            {
                "type": "text",
                "x": text_x,
                "y": value_y,
                "text": insight.key_metric_value,
                "fontSize": metric_size,
                "color": insight.theme_color,
                "weight": "bold",
                "lineHeight": 1.15,
                "maxWidth": text_max_width,
                "wrap": True,
            }
        )

    if insight.caption:
        layers.append(
            {
                "type": "text",
                "x": text_x,
                "y": caption_y,
                "text": insight.caption,
                "fontSize": 32,
                "color": "#888",
                "maxWidth": text_max_width,
            }
        )

    if insight.source:
        layers.append(
            {
                "type": "rect",
                "x": text_x,
                "y": source_y + 12,
                "width": 6,
                "height": 6,
                "color": insight.theme_color,
            }
        )
        layers.append(
            {
                "type": "text",
                "x": text_x + 18,
                "y": source_y,
                "text": insight.source,
                "fontSize": 24,
                "color": "#666",
                "maxWidth": text_max_width - 18,
            }
        )

    return {
        "canvas": {"width": w, "height": h},
        "slides": [
            {
                "background": {"color": insight.bg_color},
                "layers": layers,
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert insight markdown into slides-config.json for generate-slides.js"
        ),
    )
    parser.add_argument("insight", type=Path, help="path to insight markdown")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("slides-config.json"),
        help="output JSON path (default: ./slides-config.json)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1080,
        help="canvas width in px (default: 1080)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1440,
        help="canvas height in px; use 1920 for 9:16 (default: 1440)",
    )
    args = parser.parse_args(argv)

    content = args.insight.read_text(encoding="utf-8")
    fields = parse_frontmatter(content)
    insight = insight_from_frontmatter(fields)
    config = build_slides_config(insight, Canvas(args.width, args.height))
    args.output.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.output} "
        f"({len(config['slides'][0]['layers'])} layers, "
        f"{args.width}x{args.height})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
