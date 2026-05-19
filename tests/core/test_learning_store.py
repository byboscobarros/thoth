from pathlib import Path

from thoth.core.learning_store import FileLearningStore, InMemoryLearningStore


def test_inmemory_learning_store_appends_and_loads_updates() -> None:
    store = InMemoryLearningStore(max_updates=3)

    store.append([
        {"candidate_id": "c1", "decision": "persist", "content": "a"},
        {"candidate_id": "c2", "decision": "persist", "content": "b"},
    ])
    store.append([
        {"candidate_id": "c3", "decision": "persist", "content": "c"},
        {"candidate_id": "c4", "decision": "persist", "content": "d"},
    ])

    loaded = store.load()
    assert len(loaded) == 3
    assert loaded[0]["candidate_id"] == "c2"
    assert loaded[-1]["candidate_id"] == "c4"


def test_file_learning_store_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "learning" / "memory_updates.json"
    first = FileLearningStore(path, max_updates=10)

    first.append([
        {"candidate_id": "c1", "decision": "persist", "content": "prefiro respostas curtas"}
    ])

    second = FileLearningStore(path, max_updates=10)
    loaded = second.load()

    assert len(loaded) == 1
    assert loaded[0]["candidate_id"] == "c1"
