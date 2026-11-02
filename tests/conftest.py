"""Shared fixtures. Keep the UI env file away from the real home directory."""

import pytest

from tlgrm import envfile


@pytest.fixture(autouse=True)
def _isolate_ui_env(monkeypatch, tmp_path):
    envfile.reset_for_tests()
    monkeypatch.setenv("TG_UI_ENV", str(tmp_path / "ui.env"))
    yield
    envfile.reset_for_tests()
