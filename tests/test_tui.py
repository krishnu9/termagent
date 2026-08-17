from termagent.tui import TermagentApp, run_app


def test_app_class_exists() -> None:
    assert TermagentApp is not None
    assert callable(run_app)
