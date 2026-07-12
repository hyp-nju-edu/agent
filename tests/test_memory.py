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
