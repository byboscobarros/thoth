from thoth.domain.session_compaction import (
    CompactionMeta,
    SessionSummary,
    compaction_meta_from_data,
    summary_from_data,
)


def test_session_summary_normalizes_structured_fields() -> None:
    summary = SessionSummary(
        short="abc",
        structured={
            "facts": ["a", "a", ""],
            "goals": ["g1", 1],
            "decisions": ["d1"],
            "open_tasks": ["t1"],
            "unknown": ["x"],
        },
    )

    assert summary.structured["facts"] == ["a"]
    assert summary.structured["goals"] == ["g1"]
    assert "unknown" not in summary.structured


def test_summary_from_data_uses_defaults_for_invalid_payload() -> None:
    summary = summary_from_data({"session_summary": "invalid"})

    assert summary.version == 1
    assert summary.short == ""
    assert summary.structured == {
        "facts": [],
        "goals": [],
        "decisions": [],
        "open_tasks": [],
    }


def test_compaction_meta_from_data_reads_valid_payload() -> None:
    meta = compaction_meta_from_data(
        {
            "compaction_meta": {
                "total_messages_seen": 40,
                "total_messages_compacted": 20,
                "last_compaction_at": "2026-05-14T00:00:00+00:00",
                "last_compacted_request_id": "req_9",
            }
        }
    )

    assert isinstance(meta, CompactionMeta)
    assert meta.total_messages_seen == 40
    assert meta.total_messages_compacted == 20
    assert meta.last_compacted_request_id == "req_9"
