import json
from pathlib import Path

import pytest

from tools.insight_to_slides import (
    Canvas,
    Insight,
    build_slides_config,
    hook_font_size,
    insight_from_frontmatter,
    main,
    metric_font_size,
    parse_frontmatter,
    strip_inline_comment,
)


def test_strip_inline_comment_preserves_hash_inside_quotes():
    assert strip_inline_comment('"#ff6b35"   # 主题色') == '"#ff6b35"'


def test_strip_inline_comment_removes_trailing_comment():
    assert strip_inline_comment("foo bar # tail") == "foo bar"


def test_strip_inline_comment_no_comment():
    assert strip_inline_comment("plain value") == "plain value"


def test_parse_frontmatter_basic():
    md = '---\nhook: "测试钩子"\nbg_color: "#1a0e0a"   # 背景色\n---\n\nbody'
    assert parse_frontmatter(md) == {"hook": "测试钩子", "bg_color": "#1a0e0a"}


def test_parse_frontmatter_skips_empty_and_commented_lines():
    md = '---\n# top-level comment\n\nhook: "x"\n---\n'
    assert parse_frontmatter(md) == {"hook": "x"}


def test_parse_frontmatter_requires_open_delim():
    with pytest.raises(ValueError, match="frontmatter delimiter"):
        parse_frontmatter("no delim here")


def test_parse_frontmatter_requires_close_delim():
    with pytest.raises(ValueError, match="not closed"):
        parse_frontmatter("---\nhook: x\n")


def test_insight_from_frontmatter_requires_hook():
    with pytest.raises(ValueError, match="hook"):
        insight_from_frontmatter({})
    with pytest.raises(ValueError, match="hook"):
        insight_from_frontmatter({"hook": "   "})


def test_insight_from_frontmatter_defaults():
    insight = insight_from_frontmatter({"hook": "x"})
    assert insight.theme_color == "#ff6b35"
    assert insight.bg_color == "#1a1a1a"


def test_hook_font_size_thresholds():
    assert hook_font_size("a" * 1) == 86
    assert hook_font_size("a" * 20) == 86
    assert hook_font_size("a" * 21) == 72
    assert hook_font_size("a" * 30) == 72
    assert hook_font_size("a" * 31) == 64
    assert hook_font_size("a" * 60) == 64


def test_metric_font_size_examples_from_spec():
    assert metric_font_size("$19.0B") == 96
    assert metric_font_size("SK海力士 52% · 三星 38% · 美光 10%") == 44


def test_metric_font_size_scales_down_monotonically():
    sizes = [metric_font_size("x" * n) for n in (4, 8, 12, 18, 25)]
    assert sizes == sorted(sizes, reverse=True)


def test_build_slides_config_default_canvas_and_background():
    config = build_slides_config(Insight(hook="x"), Canvas())
    assert config["canvas"] == {"width": 1080, "height": 1440}
    assert config["slides"][0]["background"]["color"] == "#1a1a1a"


def test_build_slides_config_left_color_bar_is_first_layer():
    layers = build_slides_config(Insight(hook="x", theme_color="#abcdef"), Canvas())[
        "slides"
    ][0]["layers"]
    bar = layers[0]
    assert bar["type"] == "rect"
    assert bar["x"] == 0
    assert bar["y"] == 0
    assert bar["height"] == 1440
    assert bar["color"] == "#abcdef"


def test_build_slides_config_hook_layer_white_and_bold():
    insight = Insight(hook="为什么 HBM 重要")
    layers = build_slides_config(insight, Canvas())["slides"][0]["layers"]
    hook_layer = next(layer for layer in layers if layer.get("text") == insight.hook)
    assert hook_layer["color"] == "#fff"
    assert hook_layer["weight"] == "bold"
    assert hook_layer["wrap"] is True


def test_build_slides_config_metric_uses_theme_color_and_short_size():
    insight = Insight(hook="x", theme_color="#ff6b35", key_metric_value="$19.0B")
    layers = build_slides_config(insight, Canvas())["slides"][0]["layers"]
    metric = next(layer for layer in layers if layer.get("text") == "$19.0B")
    assert metric["color"] == "#ff6b35"
    assert metric["fontSize"] == 96


def test_build_slides_config_omits_empty_optional_fields():
    layers = build_slides_config(Insight(hook="x"), Canvas())["slides"][0]["layers"]
    text_values = [layer.get("text") for layer in layers if layer["type"] == "text"]
    # only the hook should render when every optional field is empty
    assert text_values == ["x"]


def test_build_slides_config_supports_9_16_canvas():
    config = build_slides_config(Insight(hook="x"), Canvas(1080, 1920))
    assert config["canvas"] == {"width": 1080, "height": 1920}
    bar = config["slides"][0]["layers"][0]
    assert bar["height"] == 1920


def test_build_slides_config_long_hook_uses_smaller_font():
    long_hook = "为" * 35
    layers = build_slides_config(Insight(hook=long_hook), Canvas())["slides"][0][
        "layers"
    ]
    hook_layer = next(layer for layer in layers if layer.get("text") == long_hook)
    assert hook_layer["fontSize"] == 64


def test_main_writes_valid_json(tmp_path: Path):
    insight_md = tmp_path / "insight.md"
    insight_md.write_text(
        "---\n"
        'hook: "为什么 HBM 是这轮 AI 浪潮的真瓶颈?"\n'
        'context: "HBM 供应链 · 2027"\n'
        'theme_color: "#ff6b35"\n'
        'bg_color: "#1a0e0a"\n'
        'key_metric_label: "三家厂商市占率"\n'
        'key_metric_value: "SK海力士 52% · 三星 38% · 美光 10%"\n'
        'caption: "CoWoS 产能仍是 2026 主要约束"\n'
        'source: "TrendForce, 2026年4月"\n'
        "---\n",
        encoding="utf-8",
    )
    out = tmp_path / "config.json"
    assert main([str(insight_md), "-o", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["canvas"]["width"] == 1080
    assert data["slides"][0]["background"]["color"] == "#1a0e0a"
    text_layers = [
        layer for layer in data["slides"][0]["layers"] if layer["type"] == "text"
    ]
    assert any("HBM" in (layer.get("text") or "") for layer in text_layers)


def test_main_honors_custom_canvas_size(tmp_path: Path):
    insight_md = tmp_path / "insight.md"
    insight_md.write_text(
        '---\nhook: "短"\n---\n',
        encoding="utf-8",
    )
    out = tmp_path / "config.json"
    assert (
        main([str(insight_md), "-o", str(out), "--width", "1080", "--height", "1920"])
        == 0
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["canvas"] == {"width": 1080, "height": 1920}
