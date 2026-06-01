# CLAUDE.md

> Guidance for AI assistants (Claude Code and others) working in this repository.
>
> This file is kept in sync with [AGENTS.md](AGENTS.md). The sections below extend
> the directives there with codebase structure, workflows, and conventions.
> **IMPORTANT: Review [AGENTS.md](AGENTS.md) before beginning any work** — it holds
> the authoritative coding environment, architecture principles, and cognitive workflow.

## What this project is

**Free Claude Code** is a lightweight FastAPI proxy that lets Claude Code CLI / VSCode
talk to non-Anthropic model backends without an Anthropic API key. It accepts Anthropic
Messages API requests (`POST /v1/messages`) and translates them to/from OpenAI-compatible
providers, streaming responses back in Anthropic SSE format.

Supported providers (each addressed by a `provider_prefix/model/name` string):

| Provider   | `MODEL` prefix    | API key var          | Default base URL              | Local? |
| ---------- | ----------------- | -------------------- | ----------------------------- | ------ |
| NVIDIA NIM | `nvidia_nim/...`  | `NVIDIA_NIM_API_KEY` | `integrate.api.nvidia.com/v1` | no     |
| OpenRouter | `open_router/...` | `OPENROUTER_API_KEY` | `openrouter.ai/api/v1`        | no     |
| DeepSeek   | `deepseek/...`    | `DEEPSEEK_API_KEY`   | `api.deepseek.com`            | no     |
| LM Studio  | `lmstudio/...`    | (none)               | `localhost:1234/v1`           | yes    |
| llama.cpp  | `llamacpp/...`    | (none)               | `localhost:8080/v1`           | yes    |

It also ships an optional **Discord / Telegram bot** for driving Claude Code remotely,
with tree-based message threading, session persistence, and optional voice-note transcription.

## Coding environment

- **Python 3.14** (`.python-version` pins `3.14.0`), managed with **astral `uv`**.
- Always run code/tools through `uv run ...`, never the global `python`.
- Read `.env.example` for the full set of environment variables; copy to `.env` to configure.
- Ruff is targeted at `py314` (e.g. parenthesis-free multi-exception `except TypeError, ValueError:`).
- Do **not** add `# type: ignore` / `# ty: ignore` — CI greps for these and fails the build. Fix the root cause.

## Repository layout

```
free-claude-code/
├── server.py                 # Entry point; exposes `app` / `create_app` for uvicorn
├── claude-pick                # Bash interactive model picker (writes .env, launches claude)
├── api/                       # FastAPI layer
│   ├── app.py                 # App factory + lifespan (startup/shutdown, bot wiring)
│   ├── routes.py              # /v1/messages, /v1/messages/count_tokens, /v1/models, /health, /stop
│   ├── detection.py           # Classify trivial/special requests (quota, title, prefix, suggestion, filepath)
│   ├── optimization_handlers.py # Short-circuit those requests locally (try_optimizations)
│   ├── dependencies.py        # Auth (require_api_key), provider lifecycle
│   ├── request_utils.py / command_utils.py # Request shaping helpers
│   └── models/                # Pydantic models: anthropic.py (requests), responses.py
├── providers/                 # Model backend adapters
│   ├── base.py                # ProviderConfig + BaseProvider ABC (implement stream_response)
│   ├── openai_compat.py       # OpenAICompatibleProvider base for OpenAI-shaped APIs
│   ├── rate_limit.py          # Rolling-window throttle + 429 backoff + concurrency cap
│   ├── exceptions.py          # ProviderError hierarchy
│   ├── common/                # SHARED utilities (see Architecture principles)
│   │   ├── message_converter.py   # Anthropic <-> OpenAI message conversion
│   │   ├── sse_builder.py         # Build Anthropic SSE event stream
│   │   ├── think_parser.py        # Parse <think> tags / reasoning_content -> thinking blocks
│   │   ├── heuristic_tool_parser.py # Recover tool calls emitted as plain text
│   │   ├── error_mapping.py, text.py, utils.py
│   ├── nvidia_nim/ open_router/ deepseek/  # client.py (+ request.py) per provider
│   └── lmstudio/ llamacpp/                  # local providers, client.py only
├── messaging/                 # Discord/Telegram bot
│   ├── platforms/             # MessagingPlatform ABC + discord.py, telegram.py, factory.py
│   ├── rendering/             # Platform-specific markdown rendering
│   ├── trees/                 # Tree-based threading: queue_manager, processor, repository, data
│   ├── handler.py             # ClaudeMessageHandler — drives a CLI session from chat events
│   ├── session.py, event_parser.py, limiter.py, transcription.py, transcript.py
├── config/                    # settings.py (pydantic-settings), nim.py, logging_config.py
├── cli/                       # entrypoints.py (serve/init), manager.py, session.py, process_registry.py
├── tests/                     # Pytest suite mirroring the package layout (api/ cli/ config/ messaging/ providers/)
├── nvidia_nim_models.json     # Cached NIM model catalogue (used by claude-pick)
└── pyproject.toml             # Deps, ruff/ty/pytest config, console scripts
```

## How requests flow

1. Claude Code POSTs an Anthropic request to `/v1/messages` (`api/routes.py`).
2. `api/dependencies.py:require_api_key` authenticates (optional `ANTHROPIC_AUTH_TOKEN`).
3. `api/detection.py` + `optimization_handlers.py:try_optimizations` short-circuit five
   classes of trivial calls locally (quota checks, title generation, prefix/suggestion
   detection, filepath extraction) to save quota and latency — each toggleable via env vars.
4. Otherwise `config/settings.py:resolve_model()` maps the Claude model name (opus/sonnet/haiku)
   to a configured `provider/model` string; the matching provider is selected.
5. The provider (`providers/...`) converts the request (`common/message_converter.py`),
   streams from the backend, parses thinking/tool output, and re-emits Anthropic SSE
   via `common/sse_builder.py`.

## Console scripts / running

```bash
uv sync                                   # install deps (add --extra voice / voice_local for transcription)
uv run free-claude-code                   # serve the proxy (cli/entrypoints.py:serve)
uv run fcc-init                            # scaffold config (cli/entrypoints.py:init)
uv run uvicorn server:app --host 0.0.0.0 --port 8082 --timeout-graceful-shutdown 5
./claude-pick                             # interactive model picker, then launch claude
```

Point Claude Code at the proxy by setting `ANTHROPIC_BASE_URL=http://localhost:8082`.

## Development workflow & required checks

Run the full check suite **in this order** before committing — all five are enforced by
`.github/workflows/tests.yml` (CI runs on push/PR to `main`/`master`):

```bash
uv run ruff format          # 1. format (CI uses `ruff format --check`)
uv run ruff check           # 2. lint  (E,W,F,I,UP,B,C4,SIM,PERF,RUF; line-length 88)
uv run ty check             # 3. type check (ty, target py314)
uv run pytest               # 4. tests (-n auto via pytest-xdist; 56 files, ~800 tests)
# 5. CI also greps the tree and fails on any `# type: ignore` / `# ty: ignore`
```

Always **add tests** (including edge cases) for new behaviour; the suite under `tests/`
mirrors the package layout. Use `pytest-asyncio` for async paths.

## Conventions for AI assistants

These mirror AGENTS.md — keep changes consistent with them:

- **Shared utilities live in `providers/common/`.** Never import one provider's utils from
  another provider. Extract shared logic to `common/` or a base class.
- **DRY via base classes.** OpenAI-shaped backends extend `OpenAICompatibleProvider`;
  fully custom ones extend `BaseProvider` and implement `stream_response()`.
- **Encapsulation.** Use accessor methods (e.g. `set_current_task()`), not external
  `_attribute` assignment.
- **Config over literals.** Read from `config/settings.py` (e.g. `settings.provider_type`),
  not hardcoded strings like `"nvidia_nim"`. Provider-specific fields go in the provider's
  constructor, not the shared `ProviderConfig`.
- **Platform-agnostic naming** in shared messaging code (e.g. `PLATFORM_EDIT`, not `TELEGRAM_EDIT`).
- **Backward compatibility.** When moving modules, leave re-exports at the old path.
- **No dead code / no type-ignores.** Remove unused code; fix type errors at the source.
- **Performance.** Accumulate strings in lists (avoid `+=` in loops), cache env vars at init,
  prefer iterative over deep recursion.

## Extending the system

**New OpenAI-compatible provider** — subclass `OpenAICompatibleProvider`:

```python
from providers.openai_compat import OpenAICompatibleProvider
from providers.base import ProviderConfig

class MyProvider(OpenAICompatibleProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config, provider_name="MYPROVIDER",
                         base_url="https://api.example.com/v1", api_key=config.api_key)
```

**Fully custom provider** — subclass `BaseProvider` and implement `stream_response()`.

**New messaging platform** — subclass `MessagingPlatform` (`messaging/platforms/base.py`)
and implement `start()`, `stop()`, `send_message()`, `edit_message()`, `on_message()`;
register it in `messaging/platforms/factory.py`.

## Key environment variables

See `.env.example` for the complete list. Most-used:

- `MODEL`, `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU` — per-tier model mapping (`provider/model/name`).
- `NVIDIA_NIM_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY` — provider keys.
- `LM_STUDIO_BASE_URL`, `LLAMACPP_BASE_URL` — local provider endpoints.
- `ENABLE_THINKING` — global toggle for reasoning requests / Claude thinking blocks.
- `PROVIDER_RATE_LIMIT` / `PROVIDER_RATE_WINDOW` / `PROVIDER_MAX_CONCURRENCY` — throttling.
- `ANTHROPIC_AUTH_TOKEN` — optional server-side auth for the proxy.
- `MESSAGING_PLATFORM` (`telegram`|`discord`) + the corresponding bot token / allow-list.
- `ENABLE_*` optimization toggles (`enable_title_generation_skip`, etc.).

## Summary standard for changes

When reporting work, be technical and granular. Include: **[Files Changed]**,
**[Logic Altered]**, **[Verification Method]**, **[Residual Risks]** (state "none" if none).
