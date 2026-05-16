# Khoj 检索 Prompt 模板

为 AI 算力供应链研究而设计的一组结构化检索模板,直接复制粘贴到 Khoj chat 即可使用。

底层栈假设:
- Khoj 作为 RAG 检索层
- Ollama + Qwen3.6-27B 作为本地推理模型
- 索引内容:SEC 10-K/10-Q(markdown)、卖方研报(MinerU 清洗后的 markdown)、TrendForce Excel、Obsidian 笔记

---

## 使用前须知

1. **建议在 Khoj 里开一个专用 Agent**,系统 prompt 设为:

   > 你是严格的 RAG 助手。只输出我提供的文档中能找到原文支撑的内容。找不到就明确说"无"。不要总结、不要推断、不要添加任何文档外的常识。所有数字和论断必须可追溯到具体文档名 + 章节/页码。

   这样下面所有模板都不需要每次重复"严禁编造"。

2. **本地 Qwen3.6 对严格 JSON 格式不稳定**,所以下面所有输出格式都用 **markdown 表格**,容错更高。

3. **温度建议 0 或 0.1**(在 Khoj 的模型设置里调)。表格类输出温度高了会乱排版。

4. **占位符约定**:模板里 `[METRIC]`、`[TICKER]`、`[DOC_NAME]` 这种方括号字段,粘贴时替换成你的实际值。

5. **版权红线**:所有模板都要求输出时把投行名换成"研报A / 研报B",避免内容里出现可追溯的研报名称。

---

## 模板 1:非共识观点挖掘

### 触发场景

- 已经索引了 3 份以上对同一标的(NVDA / TSM / AVGO / GOOGL 等)的卖方研报
- 你准备做"投资冷知识"内容,想找一个"卖方观点分歧最大的点"作为 hook
- 用于产出反直觉断言:"原来 GS 和 MS 对 GB300 的看法差这么多"

### 检索 prompt

```
请仅从我索引的研究报告中提取关于 [TICKER] 的观点。

任务:找出不同研报之间分歧最大的 3 个观点 —— 同一指标 / 同一时间维度,
但结论相反或差异显著(>20%)。

仅输出以下 markdown 表格,不要任何前后散文:

| # | 议题 | 研报A 观点 | 研报B 观点 | 数据点(若有) | 分歧来源(假设/方法/数据口径) |
|---|---|---|---|---|---|

规则:
- 只填能在文档中找到原文支撑的内容
- 找不到 3 个就输出 1 或 2 个,宁缺毋滥
- 研报一律写"研报A / 研报B / 研报C",绝不出现投行名(版权)
- "分歧来源"用一句话定性:是假设差异、方法差异、还是数据口径差异
```

### 输出格式

- Markdown 表格,5 列
- 每行一个分歧议题
- 不要散文 / 不要解释 / 不要"以上是分析..."
- 不要透露研报投行名(只用代号)

### 示例

**输入**:把 prompt 中的 `[TICKER]` 替换为 `NVDA`,粘到 Khoj chat。

**预期输出**:

```
| # | 议题 | 研报A 观点 | 研报B 观点 | 数据点 | 分歧来源 |
|---|---|---|---|---|---|
| 1 | 2026 GB300 出货节奏 | 上半年放量,下半年减速 | 全年线性,Q4 走强 | A: 2.4M units;B: 2.7M units | 客户提货意愿假设不同 |
| 2 | 中国市场敞口 | 视为长期归零 | 假设 H20-Next 获批 | A: $0;B: $4.2B | 监管假设差异 |
| 3 | 软件订阅收入 ARR | 2027 达 $15B | 2027 达 $8B | - | 计入 CUDA 授权的口径不同 |
```

**用法**:这张表里"分歧来源"那列就是冷知识的种子。挑一行 → 喂给模板 4(信息饲料 → insight)生成 `insight.md`。

---

## 模板 2:数据点交叉验证

### 触发场景

- 你准备在内容里引用一个具体数字(如"2025 Q3 HBM 总出货量")
- 想知道 SEC 财报 / 卖方研报 / TrendForce 三个来源对同一指标的差异
- 避免出现"研报说 2.1M,但 SEC 披露 1.7M"这种被打脸的情况

### 检索 prompt

```
请对 [METRIC] 在 [PERIOD] 的数据,从我的知识库中分类提取:

1. 来自 SEC 财报的口径(只看 10-K / 10-Q)
2. 来自卖方研报的口径
3. 来自 TrendForce / 行业数据 / Bloomberg 公开报道的口径

仅输出以下 markdown 表格:

| 来源类型 | 文档名 | 报告日期 | 口径/单位 | 数值 | 原文锚点(页码/章节/sheet) |
|---|---|---|---|---|---|

规则:
- 数值必须在文档中有原文支撑,不得推算、不得换算单位
- 口径不一致时(如 "出货量" vs "营收"),原样列出,口径列写清楚
- 文档名照实写(包括 SEC 文件名、Excel 文件名);仅卖方研报用"研报A/B/C"代号
- 找不到就明确写"无",不要编造
```

### 输出格式

- Markdown 表格,6 列
- 三类来源各自一行或多行
- 必须带原文锚点(页码 / 章节号 / sheet 名),否则不可用

### 示例

**输入**:
- `[METRIC]` = HBM3e 出货量
- `[PERIOD]` = 2025 Q3

**预期输出**:

```
| 来源类型 | 文档名 | 报告日期 | 口径/单位 | 数值 | 原文锚点 |
|---|---|---|---|---|---|
| SEC | SK_Hynix_10Q_Q3_2025.md | 2025-10-28 | "Bit Shipment, HBM3e" (QoQ %) | +47% | p.12 §"Memory Operating Results" |
| SEC | Micron_10Q_Q4_FY2025.md | 2025-09-25 | "HBM revenue" (US$ M) | $1,840M | p.9 §"Segment Results" |
| 卖方研报 | 研报A | 2025-11-02 | "Shipped units, total HBM" | 2.1M units | §3.2 fig.4 |
| 卖方研报 | 研报B | 2025-10-15 | "HBM bit shipment" (Gb) | 720 Gb (industry total) | §2.1 |
| TrendForce | hbm_monthly_2025_11.xlsx | 2025-11-15 | "Sales volume, 12-Hi HBM3e" | 1.78M units | Sheet "Q3 actual" |
```

**用法**:看到口径不一致(units vs Gb vs revenue),不要硬换算 —— 直接把"三个来源口径都不同"本身做成冷知识。

---

## 模板 3:被忽视的注脚

### 触发场景

- 你准备引用某份研报的核心结论
- 想先看清楚研报作者自己埋在 footnote / disclaimer / appendix 里的"打折声明"
- 这是最容易出冷知识的地方:作者自己都标了"if X then Y",但读者只看了主图

### 检索 prompt

```
请从我索引的 [DOC_NAME] 中,提取以下三类内容,合并输出:

1. 所有脚注(footnote)中包含数字、口径调整或方法论说明的条目
2. 所有 disclaimer / risk factor 中与本报告核心结论直接相关的免责语句
3. appendix 里被作者标注为 "sensitivity" / "scenario" / "if X, then Y" 的反向情况

仅输出以下 markdown 表格,不要前后散文:

| 类型 | 原文摘录(≤80 字) | 章节/页码 | 对主结论的潜在影响 |
|---|---|---|---|

规则:
- 摘录必须是原文,不得改写、不得翻译
- "潜在影响"用一句话陈述,不要长解释
- 优先选数值/假设相关的,跳过样板免责("过往表现不代表未来"这种)
- 如果是中文研报,摘录保留中文原文
```

### 输出格式

- Markdown 表格,4 列
- 原文摘录限定 80 字内
- "潜在影响"一句话,不要长篇分析

### 示例

**输入**:`[DOC_NAME]` = TSM_2026Q1_research.pdf(在 Khoj 里用 `file:"TSM_2026Q1"` 过滤)

**预期输出**:

```
| 类型 | 摘录 | 章节 | 潜在影响 |
|---|---|---|---|
| Footnote | "CoWoS capacity assumption excludes Phoenix Fab tooling delays beyond Q2 2026" | p.18 fn.7 | 若 Phoenix 延期超 Q2,主表 CoWoS 产能假设须下调 |
| Disclaimer | "Estimates assume current export-control regime; reauthorization risk not modeled" | p.34 | 出口管制变化未纳入,情景敏感 |
| Sensitivity | "Base case yields 92%; if HBM4 ramp slips one quarter, EPS impact -$1.20" | Appendix B, p.41 | HBM4 一季度滑期就吃掉一块 EPS |
```

**用法**:第 3 行"HBM4 滑期 -$1.20 EPS"就是典型冷知识素材 —— 主图给你看的是 base case,真正的故事在 appendix。

---

## 模板 4(Bonus):信息饲料 → insight.md 草稿

### 触发场景

- 你已经用模板 1 / 2 / 3 挖出了素材
- 想直接转成可喂给 `tools/insight_to_slides.py` 的 frontmatter 草稿
- 把"研究输出"和"内容生产"之间的手工搬运拿掉

### 检索 prompt

```
基于我刚才几轮提问的输出,请生成一份"投资冷知识"卡片草稿,
严格按下面 YAML frontmatter 模板,不要任何前后散文。

字段约束:
- hook:问句或反直觉断言,15-25 字,中文
- context:主题/时间标签,≤15 字
- theme_color:固定 "#ff6b35"(除非我另行指定)
- bg_color:固定 "#1a0e0a"
- key_metric_label:数字的一句话说明,≤12 字
- key_metric_value:1 个数字或并列结构(用 · 分隔),≤22 字
- caption:补充说明,≤20 字
- source:严禁填投行名,只填 SEC / TrendForce / Bloomberg / 公开报道 / Excel 文件名 / 公司财报披露

输出格式(直接可保存为 .md 文件):

---
hook: "..."
context: "..."
theme_color: "#ff6b35"
bg_color: "#1a0e0a"
key_metric_label: "..."
key_metric_value: "..."
caption: "..."
source: "..."
---
```

### 输出格式

YAML frontmatter 块,8 个字段,可直接保存为 `insights/xxx.md`。

### 示例

**输入序列**(在 Khoj 同一个对话里依次执行):

1. 跑模板 1,得到 NVDA 的非共识观点表
2. 接着粘上面这段 prompt(模板 4)

**预期输出**(直接保存为 `insights/nvda_china_split.md`):

```
---
hook: "为什么两家头部投行对 NVDA 中国敞口判断差 42 亿美金?"
context: "NVDA 监管 · 2026 展望"
theme_color: "#ff6b35"
bg_color: "#1a0e0a"
key_metric_label: "两家研报对 2026 中国营收预测差"
key_metric_value: "$0 vs $4.2B"
caption: "差异不在数据,在 H20-Next 是否获批的假设"
source: "NVDA FY2026 Q1 10-Q + 行业公开报道"
---
```

**用法**:

```bash
uv run python tools/insight_to_slides.py insights/nvda_china_split.md \
  -o ~/work/slides-renderer/slides-config.json
cd ~/work/slides-renderer && node generate-slides.js
```

---

## 常见坑

| 症状 | 可能原因 | 处理 |
|---|---|---|
| Khoj 输出包含"以上是基于我的知识..."这种散文 | Qwen3.6 没遵守"仅输出表格"的指令 | 在 prompt 末尾加一句"再次强调:除表格外不要输出任何其他文字" |
| 数字看着像编的、找不到出处 | 检索没命中文档,模型 fallback 到训练知识 | 在 Khoj 用 `file:` 过滤强制限定文档范围;或者改用更小的检索窗口 |
| 表格列对不齐 | markdown 输出温度过高 | 模型温度调到 0,或在 prompt 加"严格 markdown 表格语法" |
| 出现"Goldman Sachs"等投行名 | 模板没强调代号化 | 检查 prompt 是否包含"绝不出现投行名"那条,必要时再加一遍 |
| frontmatter 引号被吞了 | Qwen 偶尔会把 `"..."` 输出成 `「...」` | 输出后人工 sed 一遍,或在 prompt 加"所有 value 必须用英文双引号包裹" |

---

## 推荐工作流

```
[Khoj 检索] --模板1/2/3--> 结构化素材表
        |
        v
[Khoj 检索] --模板4-----> insights/xxx.md(frontmatter 草稿)
        |
        v
[本地 CLI ] --insight_to_slides.py--> slides-config.json
        |
        v
[本地 Node] --generate-slides.js----> output/xxx.png
        |
        v
[发布]   小红书 / YouTube Shorts
```

整条链路除"发布"那一步,全部本地完成,无云依赖、无版权外泄。
