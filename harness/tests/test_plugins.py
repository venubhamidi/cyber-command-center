import pytest
from fastapi.testclient import TestClient

from harness import plugins
from harness.plugins.secrets import FileSecrets, secrets_for
from harness.tests.conftest import READER, base_settings


def test_builtin_plugins_are_registered():
    plugins.load()
    assert {"static", "oidc"} <= set(plugins.available("auth"))
    assert {"mock", "anthropic"} <= set(plugins.available("llm"))
    assert {"env", "file"} <= set(plugins.available("secrets"))
    assert {"memory", "servicenow"} <= set(plugins.available("ticketing"))


def test_unknown_plugin_error_names_the_available_ones(database_url):
    with pytest.raises(plugins.PluginNotFound, match="Available: .*static"):
        plugins.create("auth", "ldap", base_settings(database_url))


def test_application_plugin_is_loaded_from_plugin_modules_and_selected_by_settings(make_app):
    app = make_app(plugin_modules=["harness.tests.sample_plugin"], ticketing_provider="sample")
    assert type(app.state.ticketing).__name__ == "SampleTicketing"
    r = TestClient(app).post("/api/v1/tickets", headers=READER)
    assert r.status_code == 200 and r.json()["number"] == "TKT0000001"


def test_no_ticketing_configured_is_a_clear_503(make_app):
    assert TestClient(make_app()).post("/api/v1/tickets", headers=READER).status_code == 503


def test_secrets_from_env_and_file(database_url, monkeypatch, tmp_path):
    monkeypatch.setenv("MY_SECRET", "from-env")
    assert secrets_for(base_settings(database_url)).get("MY_SECRET") == "from-env"
    (tmp_path / "MY_SECRET").write_text("from-file\n")
    files = secrets_for(base_settings(database_url, secrets_provider="file", secrets_dir=str(tmp_path)))
    assert files.get("MY_SECRET") == "from-file"
    assert files.get("MISSING") is None


def test_file_secret_name_cannot_be_a_path(tmp_path):
    (tmp_path / "inner").mkdir()
    (tmp_path / "outside").write_text("x")
    assert FileSecrets(str(tmp_path / "inner")).get("../outside") is None
