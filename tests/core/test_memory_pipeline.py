from thoth.core.memory_pipeline import MemoryPipeline, MemoryPipelineConfig
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole


def test_memory_pipeline_processes_candidates_and_decisions() -> None:
    pipeline = MemoryPipeline(
        config=MemoryPipelineConfig(
            persist_threshold=0.70,
            review_threshold=0.50,
            max_candidates=5,
        )
    )

    candidates, updates = pipeline.process(
        request_id="req_1",
        session_id="sess_1",
        input_messages=[
            RuntimeMessage(role=RuntimeMessageRole.USER, content="prefiro respostas curtas"),
        ],
        assistant_message="vamos seguir com esse padrao",
        session_summary="objetivo: implementar camada 4",
        previously_persisted_contents=set(),
    )

    assert len(candidates) == 3
    assert len(updates) == 3
    assert any(update.decision.value == "persist" for update in updates)
