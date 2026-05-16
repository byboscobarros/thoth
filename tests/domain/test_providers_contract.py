from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.providers import (
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
)


def test_provider_request_and_response_models_are_instantiable() -> None:
    request = ProviderRequest(
        request_id="req_1",
        model="mock-model",
        messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
        temperature=0.3,
        max_tokens=256,
    )

    response = ProviderResponse(
        request_id=request.request_id,
        output_text="ok",
        messages=[RuntimeMessage(role=RuntimeMessageRole.ASSISTANT, content="ok")],
        usage={"input_tokens": 1, "output_tokens": 1},
    )

    assert request.request_id == "req_1"
    assert response.output_text == "ok"
    assert response.usage["output_tokens"] == 1


def test_provider_health_model_is_instantiable() -> None:
    health = ProviderHealth(ok=True, details="ready")

    assert health.ok is True
    assert health.details == "ready"


def test_provider_errors_expose_code_and_message() -> None:
    configuration_error = ProviderConfigurationError(code="provider.config", message="missing api key")
    execution_error = ProviderExecutionError(code="provider.exec", message="request timeout")

    assert configuration_error.code == "provider.config"
    assert configuration_error.message == "missing api key"
    assert execution_error.code == "provider.exec"
    assert execution_error.message == "request timeout"
