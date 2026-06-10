# Offline wheelhouse (Windows x64 / Python 3.12)

This folder is a **self-contained wheelhouse** for installing `drawio-mcp-server`
(including the `[normalizer]` extra, which pulls in the **anthropic** SDK) on a
machine where the corporate network blocks PyPI.

It contains pre-downloaded `.whl` files for:

- the runtime dependencies — `anthropic`, `mcp`, `pydantic`, and their full
  transitive closure (httpx, jiter, pydantic-core, cryptography, etc.);
- the build backend — `hatchling` + `editables` — needed because the project is
  installed in **editable** mode (`pip install -e`);
- `pip` / `setuptools` / `wheel`.

The compiled wheels (`pydantic_core`, `jiter`, `cryptography`, `cffi`, `rpds_py`,
`tomli`) are **`cp312` / `win_amd64`** — they only work on **Windows x64 with
Python 3.12**. For a different OS or Python version, regenerate (see below).

## How to install (offline)

`scripts\windows\setup.ps1` auto-detects this folder. Just run it as usual:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
```

When `wheels\` is present and non-empty, the script switches every `pip`
invocation to `--no-index --find-links wheels`, so nothing is fetched from PyPI.
You'll see `[OK] Offline wheelhouse detected` in the output.

The script reads the required Python version from the wheel filenames (the
`cp312` tag) and **requires that exact version** — it will not silently use a
different one. If Python 3.12 is not installed, the script reports it and skips
the install step (it does not try to install Python for you). Install Python
3.12 first — e.g. `winget install Python.Python.3.12`, or the offline installer
from <https://www.python.org/downloads/> — then re-run `setup.ps1`.

The script is **best-effort**: if any single step fails it records the problem
and continues with the remaining steps, then prints a summary of everything that
went wrong at the end (and exits non-zero). It is always safe to re-run.

To install manually instead:

```powershell
python -m pip install --no-index --find-links wheels -e "drawio-mcp-server[normalizer]"
```

## How this folder was regenerated

Downloaded from a machine that *can* reach PyPI (cross-platform download — the
download host does not need to be Windows):

```bash
pip download --only-binary=:all: \
  --platform win_amd64 --python-version 3.12 --implementation cp --abi cp312 \
  --dest wheels \
  "anthropic>=0.40" "mcp>=1.0.0" "pydantic>=2.0" \
  hatchling editables pip setuptools wheel
```

For a different target, change `--platform` (e.g. `manylinux2014_x86_64`,
`macosx_11_0_arm64`), `--python-version`, and `--abi` (e.g. `cp311`) to match.
