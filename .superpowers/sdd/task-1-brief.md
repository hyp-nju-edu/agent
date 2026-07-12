## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `sentinel/__init__.py`, `sentinel/core/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Create: `.gitignore`

**Interfaces:** Produces a runnable `pytest` invocation and an empty importable `sentinel` package.

- [ ] **Step 1: Initialize git repo**

```bash
cd E:\agent
git init
git add -A
git commit -m "chore: initial commit"
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env
*.egg-info/
dist/
build/
sentinel.db
*.db
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "sentinel-harness"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["sentinel*"]
```

- [ ] **Step 4: Create package `__init__` files**

`sentinel/__init__.py`:
```python
"""Sentinel: a coding agent harness."""
__version__ = "0.1.0"
```

`sentinel/core/__init__.py`: (empty)
```python
"""Sentinel harness core."""
```

`tests/__init__.py`: (empty file)

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 5: Install dev deps and verify pytest runs**

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```
Expected: `no tests ran` (exit 0 — collection succeeds, no tests yet). If `pytest-asyncio` warns about `asyncio_mode`, it is already set to `auto`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: scaffold sentinel package and pytest config"
```

---

