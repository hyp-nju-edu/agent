## Task 14: Memory Store

**Files:**
- Create: `sentinel/core/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces: `MemoryStore` (`add(kind, key, content)`, `search(query, limit) -> list`, uses sqlite3 + TF-IDF). Self-implemented (no framework memory).

- [ ] **Step 1: Write the failing test**

`tests/test_memory.py`:
```python
from sentinel.core.memory import MemoryStore

def test_add_and_search(tmp_path):
    store = MemoryStore(path=str(tmp_path / "mem.db"))
    store.add("convention", "testing", "always run pytest first")
    store.add("decision", "framework", "no langchain allowed")
    results = store.search("pytest testing")
    assert len(results) >= 1
    assert "pytest" in results[0].lower()

def test_search_ranks_relevant(tmp_path):
    store = MemoryStore(path=str(tmp_path / "mem.db"))
    store.add("note", "a", "the agent uses docker sandbox")
    store.add("note", "b", "pytest runs the tests")
    results = store.search("pytest")
    assert "pytest runs the tests" in results[0]

def test_empty_query_returns_any(tmp_path):
    store = MemoryStore(path=str(tmp_path / "mem.db"))
    store.add("note", "a", "something")
    assert len(store.search("")) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_memory.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/memory.py`:
```python
from __future__ import annotations
import math
import re
import sqlite3
import time
from collections import Counter


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class MemoryStore:
    """Self-implemented memory: SQLite + TF-IDF retrieval."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS memory "
            "(id INTEGER PRIMARY KEY, kind TEXT, key TEXT, content TEXT, created_at REAL)"
        )
        self._conn.commit()

    def add(self, kind: str, key: str, content: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO memory (kind, key, content, created_at) VALUES (?, ?, ?, ?)",
            (kind, key, content, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def _all(self) -> list[tuple[int, str, str, str]]:
        return self._conn.execute(
            "SELECT id, kind, key, content FROM memory"
        ).fetchall()

    def search(self, query: str, limit: int = 5) -> list[str]:
        rows = self._all()
        if not rows:
            return []
        docs = [_tokens(r[3]) for r in rows]
        n = len(docs)
        df = Counter()
        for d in docs:
            for term in set(d):
                df[term] += 1
        idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}
        q_tokens = _tokens(query)
        if not q_tokens:
            return [r[3] for r in rows[:limit]]
        scored = []
        for i, d in enumerate(docs):
            tf = Counter(d)
            score = sum(tf.get(t, 0) * idf.get(t, 0) for t in q_tokens)
            scored.append((score, rows[i][3]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [content for score, content in scored[:limit] if score > 0] or [rows[0][3]]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_memory.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/memory.py tests/test_memory.py
git commit -m "feat(memory): add self-implemented SQLite + TF-IDF MemoryStore"
```

---

