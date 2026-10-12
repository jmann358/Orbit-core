"""GitHub CLI PR publishing is explicit and keeps tokens out of ORBIT storage."""
from pathlib import Path
import tempfile
from unittest.mock import patch

from luna.github_auth import token_for_draft_pr
from luna.self_build import publishing_config, publish_review_pr
from scripts import luna_mac_service as mac
from scripts import luna_one_time_setup as setup


def test_github_cli_not_called_without_owner_opt_in():
    with patch("luna.github_auth.subprocess.run") as invoked:
        assert token_for_draft_pr({}) == ""
        invoked.assert_not_called()
    assert not publishing_config({"LUNA_GITHUB_USE_GH_CLI": "1"})["ready"]


def test_auth_token_read_only_after_explicit_opt_in():
    class Response:
        returncode = 0
        stdout = "gho_testtoken12345\n"
        stderr = ""

    with patch("luna.github_auth.shutil.which", return_value="/usr/bin/gh"):
        with patch("luna.github_auth.subprocess.run", return_value=Response()) as call:
            token = token_for_draft_pr({"LUNA_GITHUB_USE_GH_CLI": "1"})
    assert token == "gho_testtoken12345"
    assert call.call_args.args[0] == [
        "/usr/bin/gh", "auth", "token", "--hostname", "github.com"
    ]
    assert call.call_args.kwargs["timeout"] <= 10
    assert publishing_config({
        "LUNA_GITHUB_USE_GH_CLI": "1",
        "LUNA_GITHUB_PR_ENABLED": "1",
    })["ready"]
    assert not publishing_config({
        "LUNA_GITHUB_USE_GH_CLI": "1",
        "LUNA_GITHUB_PR_ENABLED": "1",
        "LUNA_GITHUB_REPOSITORY": "someone/else",
    })["ready"]


def test_unauthenticated_cli_fails_before_publication_or_network():
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "empty.db"
        with patch("luna.github_auth.token_for_draft_pr", return_value=""):
            with patch("luna.self_build.token_for_draft_pr", return_value=""):
                with patch("luna.self_build.verified_proposal") as verified:
                    try:
                        publish_review_pr(
                            database, 1,
                            environ={
                                "LUNA_GITHUB_USE_GH_CLI": "1",
                                "LUNA_GITHUB_PR_ENABLED": "1",
                            }
                        )
                    except ValueError as exc:
                        assert "not authenticated" in str(exc)
                    else:
                        assert False, "Authentication was required"
                    verified.assert_not_called()
        assert not database.exists()


def test_optional_draft_prs_require_real_local_cli_login():
    with patch("luna.github_auth.token_for_draft_pr", return_value=""):
        with patch.object(mac.sys, "platform", "darwin"):
            with patch.object(mac, "preflight", return_value=None):
                with tempfile.TemporaryDirectory() as folder:
                    home = Path(folder) / "home"
                    home.mkdir()
                    with patch("luna.github_auth.token_for_draft_pr",
                               return_value=""):
                        try:
                            mac.install(root=folder, home=home,
                                        enable_draft_prs=True)
                        except ValueError as exc:
                            assert "GitHub CLI" in str(exc)
                        else:
                            assert False
                    assert not mac.service_file(home).exists()


def test_single_setup_flag_enables_draft_prs_after_login():
    called = []
    with patch.object(setup, "require_mac", return_value=None), \
         patch.object(setup, "prepare_python", return_value=Path("/fake/python")), \
         patch.object(setup, "ensure_ollama_command", return_value="/fake/ollama"), \
         patch.object(setup, "start_model_server"), \
         patch.object(setup, "ensure_local_model"), \
         patch.object(setup, "ensure_github_login",
                      side_effect=lambda: called.append("login")), \
         patch.object(setup, "run",
                      side_effect=lambda *cmd, **kw: called.append(cmd)):
        assert setup.main(["--enable-draft-prs"]) == 0
    assert called[0] == "login"
    assert called[1][-2:] == ("--install", "--enable-draft-prs")


def test_service_settings_never_contain_a_github_token():
    config = mac.plist_config(root=Path("/test/Orbit-core"),
                              home=Path("/test/home"),
                              enable_draft_prs=True)
    env = config["EnvironmentVariables"]
    assert env["LUNA_GITHUB_PR_ENABLED"] == "1"
    assert env["LUNA_GITHUB_PR_AUTO_ENABLED"] == "1"
    assert env["LUNA_GITHUB_USE_GH_CLI"] == "1"
    assert "LUNA_GITHUB_TOKEN" not in env
