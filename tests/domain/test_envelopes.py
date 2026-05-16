import pytest

from thoth.domain.envelopes import (
    EnvelopeValidationError,
    RuntimeInputEnvelope,
    RuntimeMessage,
    RuntimeMessageRole,
    RuntimeOutputEnvelope,
    RuntimeStatus,
    validate_input_envelope,
    validate_output_envelope,
)


def test_envelopes_are_importable_and_instantiable() -> None:
    message = RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")

    runtime_input = RuntimeInputEnvelope(
        request_id="req_1",
        gateway="cli",
        input=[message],
    )
    runtime_output = RuntimeOutputEnvelope(
        request_id="req_1",
        status=RuntimeStatus.SUCCESS,
        messages=[RuntimeMessage(role=RuntimeMessageRole.ASSISTANT, content="ok")],
    )

    assert runtime_input.request_id == "req_1"
    assert runtime_output.status is RuntimeStatus.SUCCESS


def test_validate_input_envelope_success() -> None:
    envelope = RuntimeInputEnvelope(
        request_id="req_ok",
        gateway="cli",
        input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hi")],
    )

    validate_input_envelope(envelope)


def test_validate_input_envelope_invalid_schema() -> None:
    envelope = RuntimeInputEnvelope(
        schema_version="v999",
        request_id="req_ok",
        gateway="cli",
    )

    with pytest.raises(EnvelopeValidationError) as exc:
        validate_input_envelope(envelope)

    assert exc.value.code == "invalid_envelope"
    assert exc.value.issues[0].field == "schema_version"


def test_validate_input_envelope_missing_required_fields() -> None:
    envelope = RuntimeInputEnvelope(request_id="", gateway=" ")

    with pytest.raises(EnvelopeValidationError) as exc:
        validate_input_envelope(envelope)

    fields = [issue.field for issue in exc.value.issues]
    assert fields == ["gateway", "request_id"]


def test_validate_output_envelope_success() -> None:
    envelope = RuntimeOutputEnvelope(request_id="req_ok")

    validate_output_envelope(envelope)


def test_validate_output_envelope_missing_request_id() -> None:
    envelope = RuntimeOutputEnvelope(request_id="")

    with pytest.raises(EnvelopeValidationError) as exc:
        validate_output_envelope(envelope)

    assert exc.value.code == "invalid_envelope"
    assert exc.value.issues[0].field == "request_id"
