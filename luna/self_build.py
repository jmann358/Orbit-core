"""Supervised self-building: initiate bounded missions and publish review-only PRs.

GitHub publishing is strictly opt-in, targets one fixed repository and an
allowlisted source file, and never merges, runs generated code, or deploys.
No conversation records, memory database, or provider keys leave this module.
"""
import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from luna.cloud_worker import connect
from luna.developer_agent import ROOT, TEMPLATES, mission, queue_mission, status
from luna.patches import MAX_BYTES
from luna.workshop import stage_proposal

REPOSITORY = "jmann358/Orbit-core"
API_URL = "https://api.github.com"
BASE_BRANCH = "main"


def publishing_config(environ=None):
    env = os.environ if environ is None else environ
    # An environment variable is an opt-in, not an authority to target other
    # repositories or expose a private URL.
    return {
        "enabled": env.get("LUNA_GITHUB_PR_ENABLED") == "1",
        "ready": (env.get("LUNA_GITHUB_PR_ENABLED") == "1"
                  and bool(env.get("LUNA_GITHUB_TOKEN"))
                  and env.get("LUNA_GITHUB_REPOSITORY", REPOSITORY) == REPOSITORY),
        "repository": REPOSITORY,
        "approval_required_to_merge": True,
    }


def _publication_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS developer_publications (
        mission_id INTEGER PRIMARY KEY,
        state TEXT NOT NULL,
        branch TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""")


def publication(db_path, mission_id):
    with connect(db_path) as db:
        _publication_table(db)
        row = db.execute(
            "SELECT state,branch,url FROM developer_publications "
            "WHERE mission_id=?", (mission_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(zip(("state", "branch", "url"), row))


def readiness(db_path, *, environ=None):
    env = os.environ if environ is None else environ
    state = status(db_path)
    github = publishing_config(env)
    auto = env.get("LUNA_AGENT_AUTO_ENABLED") == "1"
    worker = env.get("LUNA_WORKER_ENABLED") == "1"
    # This is a readiness assessment, not an assertion that a process,
    # inference server, internet connection, or token has been verified.
    blockers = []
    if not state["model"]["ready"]:
        blockers.append("development_model_not_configured")
    if not worker:
        blockers.append("worker_not_enabled")
    if not auto:
        blockers.append("unattended_drafts_not_enabled")
    if not github["ready"]:
        blockers.append("github_pr_publishing_not_configured")
    return {
        "self_build_ready_unverified": not blockers and not state["paused"],
        "paused": state["paused"],
        "model_ready_unverified": state["model"]["ready"],
        "worker_flag_enabled": worker,
        "unattended_flag_enabled": auto,
        "github_pr": github,
        "blockers": blockers,
        "missions": state["counts"],
        "daily_attempts": state["daily_model_attempts"],
        "owner_review_required": True,
        "hosting_provisioned": False,
        "memory_migration_performed": False,
    }


def start(db_path, *, now=None):
    """Queue a concrete improvement; worker continues when a model is ready.

    This does not enable spending, connect models, or bypass a paused agent.
    It can be used from Luna's UI before credentials are configured.
    """
    state = status(db_path)
    if state["paused"]:
        raise ValueError("Luna's development agent is paused")
    now = now or datetime.now(timezone.utc)
    targets = tuple(sorted(TEMPLATES))
    # Rotate the two reviewed source targets, without permitting new paths.
    target = targets[now.date().toordinal() % len(targets)]
    queued = queue_mission(db_path, target)
    return {
        "mission_id": queued["mission_id"],
        "created": queued["created"],
        "path": target,
        "waiting_for_model": not state["model"]["ready"],
        "waiting_for_worker": os.environ.get("LUNA_WORKER_ENABLED") != "1",
        "no_code_applied": True,
    }


def verified_proposal(db_path, mission_id, *, root=None):
    """Revalidate original source, candidate and manifest immediately before PR."""
    root = ROOT if root is None else Path(root)
    item = mission(db_path, mission_id)
    if item is None or item["state"] != "review" or item["path"] not in TEMPLATES:
        raise ValueError("Only completed allowlisted proposals can be published")
    replacement = item["replacement"]
    if (not isinstance(replacement, str)
            or not 1 <= len(replacement.encode("utf-8")) <= MAX_BYTES):
        raise ValueError("Invalid bounded replacement")
    verified = stage_proposal(root, [{
        "path": item["path"], "base_sha256": item["base_sha256"],
        "replacement": replacement,
    }], tests=[])
    if (verified["fingerprint"] != item["fingerprint"]
            or verified["manifest"] != item["manifest"]
            or not verified["diffs"][0]["diff"]):
        raise ValueError("Proposal or source revision changed; new review required")
    return item


def _reply(client, method, route, *, json=None):
    try:
        response = client.request(method, route, json=json)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("GitHub returned a non-object")
        return result
    except (httpx.HTTPError, ValueError, TypeError):
        # Never expose response bodies, authorization headers or provider URLs.
        raise ValueError("GitHub operation failed; inspect the deployment log privately") from None


def publish_review_pr(db_path, mission_id, *, environ=None, root=None,
                      transport=None):
    """Publish exactly one PR; reject a retry after any uncertain failure.

    This function is explicitly opt-in and safe to call from a worker/UI.
    The GitHub token must be scoped to this repository, supplied by the
    host's secret manager. Token is never copied to model prompts or SQLite.
    """
    env = os.environ if environ is None else environ
    cfg = publishing_config(env)
    if not cfg["ready"]:
        raise ValueError("GitHub PR publishing needs explicit owner setup")
    item = verified_proposal(db_path, mission_id, root=root)
    branch = ("luna/review-" + str(mission_id) + "-"
              + item["fingerprint"][:12])
    with connect(db_path) as db:
        _publication_table(db)
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT state FROM developer_publications WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if existing:
            raise ValueError("Mission publication already attempted; no automatic retry")
        db.execute(
            "INSERT INTO developer_publications(mission_id,state,branch,created_at) "
            "VALUES(?,'publishing',?,?)",
            (mission_id, branch, datetime.now(timezone.utc).isoformat()),
        )

    route = "/repos/" + REPOSITORY
    headers = {
        "Authorization": "Bearer " + env["LUNA_GITHUB_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(base_url=API_URL, headers=headers, timeout=20,
                          follow_redirects=False, transport=transport) as client:
            head = _reply(client, "GET", route + "/git/ref/heads/" + BASE_BRANCH)
            sha = head.get("object", {}).get("sha")
            if not isinstance(sha, str) or len(sha) != 40:
                raise ValueError("GitHub base ref unavailable")
            remote = _reply(client, "GET", route + "/contents/" + item["path"]
                            + "?ref=" + BASE_BRANCH)
            if remote.get("encoding") != "base64":
                raise ValueError("GitHub source encoding is invalid")
            try:
                original = base64.b64decode(remote["content"], validate=False)
            except (KeyError, TypeError, ValueError):
                raise ValueError("GitHub source could not be validated") from None
            if (len(original) > MAX_BYTES
                    or hashlib.sha256(original).hexdigest() != item["base_sha256"]):
                raise ValueError("GitHub source changed; regenerate the proposal")
            blob = remote.get("sha")
            if not isinstance(blob, str) or len(blob) != 40:
                raise ValueError("GitHub source blob missing")
            _reply(client, "POST", route + "/git/refs", json={
                "ref": "refs/heads/" + branch, "sha": sha,
            })
            _reply(client, "PUT", route + "/contents/" + item["path"], json={
                "message": "Luna: propose reviewed improvement #" + str(mission_id),
                "branch": branch,
                "sha": blob,
                "content": base64.b64encode(
                    item["replacement"].encode("utf-8")).decode("ascii"),
            })
            result = _reply(client, "POST", route + "/pulls", json={
                "head": branch, "base": BASE_BRANCH, "draft": True,
                "title": "Luna proposed improvement #" + str(mission_id),
                "body": (
                    "Autonomously drafted source change. Owner review required.\n\n"
                    "Target: \`" + item["path"] + "\`\n\n"
                    "Summary: " + item["summary"][:400] + "\n\n"
                    "**Only syntax/bytecode compilation checked locally; full "
                    "tests and security review still required.**\n"
                    "No deploy, source application, merge, or cost authorization."
                ),
            })
            url = result.get("html_url")
            if (not isinstance(url, str) or not url.startswith(
                    "https://github.com/" + REPOSITORY + "/pull/")
                    or not url.removeprefix(
                        "https://github.com/" + REPOSITORY + "/pull/").isdigit()):
                raise ValueError("GitHub PR confirmation was invalid")
        with connect(db_path) as db:
            _publication_table(db)
            db.execute(
                "UPDATE developer_publications SET state='review',url=? "
                "WHERE mission_id=? AND state='publishing'", (url, mission_id),
            )
        return {"url": url, "mission_id": mission_id,
                "review_required": True, "merged": False}
    except Exception:
        with connect(db_path) as db:
            _publication_table(db)
            db.execute(
                "UPDATE developer_publications SET state='attention' "
                "WHERE mission_id=? AND state='publishing'", (mission_id,),
            )
        # Uncertain partial GitHub writes are not retried automatically.
        raise ValueError("PR publication needs attention; no automatic retry") from None
