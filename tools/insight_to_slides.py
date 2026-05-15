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


def build_slides_config(insight: Insight, canvas: Canvas) -> dict[str, Any]:
    w, h = canvas.width, canvas.height
    pad_x = 80
    bar_width = 12
    text_x = pad_x
    text_max_width = w - pad_x * 2

    context_y = round(h * 0.10)
    hook_y = round(h * 0.17)
    bottom_block_y = round(h * 0.72)
    source_y = h - 60

    hook_size = hook_font_size(insight.hook)
    metric_size = metric_font_size(insight.key_metric_value)

    layers: list[dict[str, Any]] = [
        {
            "type": "rect",
            "x": 0,
            "y": 0,
            "width": bar_width,
            "height": h,
            "color": insight.theme_color,
        },
    ]

    if insight.context:
        layers.append(
            {
                "type": "text",
                "x": text_x,
                "y": context_y,
                "text": insight.context,
                "fontSize": 36,
                "color": "#888",
                "maxWidth": text_max_width,
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
            "lineHeight": 1.25,
            "maxWidth": text_max_width,
            "wrap": True,
        }
    )

    metric_label_y = bottom_block_y
    metric_value_y = bottom_block_y + 60
    caption_y = metric_value_y + metric_size + 30

    if insight.key_metric_label:
        layers.append(
            {
                "type": "text",
                "x": text_x,
                "y": metric_label_y,
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
                "y": metric_value_y,
                "text": insight.key_metric_value,
                "fontSize": metric_size,
                "color": insight.theme_color,
                "weight": "bold",
                "lineHeight": 1.2,
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
                "type": "text",
                "x": text_x,
                "y": source_y,
                "text": insight.source,
                "fontSize": 24,
                "color": "#555",
                "maxWidth": text_max_width,
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
