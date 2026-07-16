from app.main import app


def test_api_has_expected_title() -> None:
    assert app.title == "CrickOps AI API"
