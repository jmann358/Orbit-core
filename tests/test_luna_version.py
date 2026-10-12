"""Release identifier used in the dashboard and API must agree."""
from fastapi.testclient import TestClient
from app import app, VERSION
from luna.release import next_version
import pytest


def test_luna_pojo_release_identifier_is_consistent():
    assert VERSION == "pojo.2"
    assert app.title == "ORBIT · Luna pojo.2"
    client = TestClient(app)
    response = client.get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "pojo.2"
    assert payload["build"] == "pojo.2"

    home = client.get("/")
    assert home.status_code == 200
    assert "<title>Luna pojo.2 · ORBIT</title>" in home.text
    assert "<small>pojo.2 · Agent Core</small>" in home.text
    assert "v1.0.0-rc.1" not in home.text


def test_owner_release_numbers_advance_in_order():
    assert next_version("pojo.1") == "pojo.2"
    assert next_version("pojo.2") == "pojo.3"
    assert next_version() == "pojo.3"
    for bad in ("1.1.2.3", "pojo.0", "pojo.02", "pojo.-1", "pojo.b", "other.2"):
        with pytest.raises(ValueError):
            next_version(bad)


def test_displayed_version_comes_from_single_release_constant():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "from luna.release import VERSION" in source
    assert 'html.replace("__LUNA_VERSION__", VERSION)' in source
    assert "<title>Luna __LUNA_VERSION__ · ORBIT</title>" in source
    assert "<small>__LUNA_VERSION__ · Agent Core</small>" in source
