import pytest
from pydantic_ai import models

models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture(autouse=True)
def _ignore_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("termagent.config.load_dotenv", lambda *args, **kwargs: False)
