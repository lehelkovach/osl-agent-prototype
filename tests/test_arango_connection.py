import pytest


def test_arango_basic_connection(arango_status):
    if arango_status["state"] == "skip":
        pytest.skip(arango_status["reason"])
    if arango_status["state"] == "fail":
        pytest.fail(arango_status["reason"])

    assert arango_status["state"] == "ok"


def test_openai_basic_connection(openai_status):
    if openai_status["state"] == "skip":
        pytest.skip(openai_status["reason"])
    if openai_status["state"] == "fail":
        pytest.fail(openai_status["reason"])

    assert openai_status["state"] == "ok"
