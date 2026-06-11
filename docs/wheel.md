# Offline Wheelhouse — Package Reference

This document explains **every `.whl` file** shipped in the [`wheels/`](../wheels/)
folder, and **why each one is needed**.

## Background

The `wheels/` folder is a **self-contained offline wheelhouse**. It exists because
the corporate network blocks PyPI, so `scripts\windows\setup.ps1` installs
`drawio-mcp-server` (plus its `[normalizer]` extra) entirely from these local
files (`pip --no-index --find-links wheels`) instead of downloading anything.

Only **three** packages are direct dependencies (`mcp`, `pydantic`, `anthropic`);
everything else is pulled in **transitively** (a dependency-of-a-dependency) or is
part of the **build toolchain** needed to install the project in editable mode.

### Wheel tags — pure vs. compiled

| Tag in filename | Meaning | Runs on |
|---|---|---|
| `...-py3-none-any.whl` | **Pure Python** — no compiled code | Any Python 3, any OS |
| `...-cp314-cp314-win_amd64.whl` | **Compiled** for CPython 3.14 | **Windows x64 + Python 3.14 only** |
| `...-cp311-abi3-win_amd64.whl` | Compiled, **stable ABI** | Windows x64 + Python **3.11 or newer** (incl. 3.14) |

> The compiled wheels are why the whole wheelhouse is locked to **one Python
> version**. They were rebuilt for **Python 3.14 (`cp314`)** to match the client's
> installed interpreter. See [`wheels/README.md`](../wheels/README.md) to regenerate.

---

## 1. Direct dependencies (declared in `pyproject.toml`)

| Wheel | Version | Type | Why it's needed |
|---|---|---|---|
| `mcp` | 1.27.2 | pure | The **Model Context Protocol** framework — the server is built on it; exposes the draw.io tools to VS Code / Copilot. |
| `pydantic` | 2.13.4 | pure | Data validation / typed models used throughout the server and the MCP message schemas. |
| `anthropic` | 0.109.1 | pure | Claude SDK — pulled in by the `[normalizer]` extra; used by `scripts/normalize_jira_story.py` for the LLM-rewrite path. |

## 2. Compiled (version-locked) wheels — the strict ones

These contain native C/Rust code and **only work on Python 3.14 / Windows x64**.
They are the reason `setup.ps1` demands an exact Python version.

| Wheel | Version | Tag | Why it's needed |
|---|---|---|---|
| `pydantic_core` | 2.46.4 | `cp314` | The compiled Rust core that powers **pydantic** — the heavy lifting of validation. |
| `jiter` | 0.15.0 | `cp314` | Fast JSON parser used by the **anthropic** SDK for streaming responses. |
| `rpds_py` | 2026.5.1 | `cp314` | Persistent data structures used by `referencing` → **jsonschema** (an `mcp` dep). |
| `cffi` | 2.0.0 | `cp314` | C foreign-function interface — required by **cryptography**. |
| `tomli` | 2.4.1 | `cp314` | TOML parser used by the **hatchling** build backend to read `pyproject.toml`. |
| `cryptography` | 48.0.1 | `cp311-abi3` | Crypto primitives for **pyjwt[crypto]** (an `mcp` dep). Stable-ABI wheel — runs on any 3.11+. |

## 3. Build toolchain (needed for `pip install -e` / editable mode)

| Wheel | Version | Type | Why it's needed |
|---|---|---|---|
| `hatchling` | 1.30.1 | pure | The **build backend** declared in `pyproject.toml`; builds the editable install. |
| `editables` | 0.6 | pure | Lets hatchling create the editable (`-e`) install hooks. |
| `pathspec` | 1.1.1 | pure | Hatchling dependency — gitignore-style path matching for file inclusion. |
| `pluggy` | 1.6.0 | pure | Hatchling dependency — plugin/hook management. |
| `packaging` | 26.2 | pure | Hatchling dependency — version & requirement parsing. |
| `trove_classifiers` | 2026.6.1.19 | pure | Hatchling dependency — validates PyPI classifiers. |
| `pip` | 26.1.2 | pure | Installer itself (bundled so the venv has a known-good version). |
| `setuptools` | 82.0.1 | pure | Core packaging tooling, used during builds. |
| `wheel` | 0.47.0 | pure | Builds/installs `.whl` archives. |

## 4. Transitive dependencies of `pydantic`

| Wheel | Version | Type | Why it's needed |
|---|---|---|---|
| `annotated_types` | 0.7.0 | pure | Provides the `Annotated` metadata types pydantic uses for constraints. |
| `typing_extensions` | 4.15.0 | pure | Backports of newer `typing` features used by pydantic. |
| `typing_inspection` | 0.4.2 | pure | Runtime inspection of typing annotations for pydantic v2. |

## 5. Transitive dependencies of `anthropic`

| Wheel | Version | Type | Why it's needed |
|---|---|---|---|
| `anyio` | 4.13.0 | pure | Async I/O abstraction used by the HTTP stack. |
| `httpx` | 0.28.1 | pure | HTTP client the SDK uses to call the Claude API. |
| `httpcore` | 1.0.9 | pure | Low-level HTTP transport under httpx. |
| `h11` | 0.16.0 | pure | HTTP/1.1 protocol implementation for httpcore. |
| `certifi` | 2026.5.20 | pure | Root CA certificate bundle for TLS verification. |
| `idna` | 3.18 | pure | Internationalized domain name handling for URLs. |
| `sniffio` | 1.3.1 | pure | Detects the running async library (asyncio/trio) for anyio. |
| `distro` | 1.9.0 | pure | OS/distro detection used in the SDK's request metadata. |
| `docstring_parser` | 0.18.0 | pure | Parses docstrings for the SDK's tool/function helpers. |

## 6. Transitive dependencies of `mcp`

| Wheel | Version | Type | Why it's needed |
|---|---|---|---|
| `pydantic_settings` | 2.14.1 | pure | Settings/config loading built on pydantic, used by mcp. |
| `python_dotenv` | 1.2.2 | pure | Loads `.env` files for pydantic-settings. |
| `jsonschema` | 4.26.0 | pure | Validates JSON-Schema tool definitions in the MCP protocol. |
| `jsonschema_specifications` | 2025.9.1 | pure | Bundled JSON-Schema meta-schemas for jsonschema. |
| `referencing` | 0.37.0 | pure | JSON reference resolution backing jsonschema. |
| `attrs` | 26.1.0 | pure | Class-building library used by jsonschema/referencing. |
| `pyjwt` | 2.13.0 | pure | JSON Web Token handling for MCP auth flows (`[crypto]` extra). |
| `pycparser` | 3.0 | pure | C parser required by `cffi` (→ cryptography). |
| `python_multipart` | 0.0.32 | pure | Multipart form parsing for the HTTP server transport. |
| `starlette` | 1.3.0 | pure | ASGI framework backing the MCP HTTP/SSE server transport. |
| `sse_starlette` | 3.4.4 | pure | Server-Sent Events support for starlette (MCP streaming). |
| `httpx_sse` | 0.4.3 | pure | SSE client support for httpx (MCP streaming). |
| `uvicorn` | 0.49.0 | pure | ASGI server that runs the starlette app. |
| `click` | 8.4.1 | pure | CLI parsing used by uvicorn. |
| `exceptiongroup` | 1.3.1 | pure | Backport of `ExceptionGroup` used by anyio. |

---

## How to regenerate this wheelhouse

If the client's Python version changes (e.g. to 3.13 or 3.16), the compiled
wheels must be rebuilt. From a machine that **can** reach PyPI (any OS):

```bash
pip download --only-binary=:all: \
  --platform win_amd64 --python-version 3.14 --implementation cp --abi cp314 \
  --dest wheels \
  "anthropic>=0.40" "mcp>=1.0.0" "pydantic>=2.0" \
  hatchling editables pip setuptools wheel
```

Change `--python-version` and `--abi` (e.g. `3.13` / `cp313`) to target a
different interpreter. See [`wheels/README.md`](../wheels/README.md) for details.
