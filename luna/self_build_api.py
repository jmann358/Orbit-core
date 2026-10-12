"""Owner-facing controls for Luna's staged, increasingly independent work."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from luna import core, self_build

router = APIRouter()


@router.get("/agent/self-build/status")
def bootstrap_status():
    return self_build.readiness(core.DB_PATH)


@router.post("/agent/self-build/start")
def bootstrap_start():
    try:
        return self_build.start(core.DB_PATH)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/agent/self-build/publications/{mission_id}")
def publication_status(mission_id: int):
    if mission_id < 1:
        raise HTTPException(400, "Invalid mission ID")
    return self_build.publication(core.DB_PATH, mission_id) or {"state": "not_published"}


@router.post("/agent/self-build/publish/{mission_id}")
def publish_review_only(mission_id: int):
    if mission_id < 1:
        raise HTTPException(400, "Invalid mission ID")
    try:
        return self_build.publish_review_pr(core.DB_PATH, mission_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
