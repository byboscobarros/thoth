from thoth.core.memory_redactor import MemoryRedactor


def test_memory_redactor_masks_common_sensitive_patterns() -> None:
    redactor = MemoryRedactor()

    result = redactor.redact(
        "email user@example.com token sk-1234567890abcdef numero 12345678901234"
    )

    assert result.applied is True
    assert "[redacted_email]" in result.content
    assert "[redacted_token]" in result.content
    assert "[redacted_number]" in result.content
