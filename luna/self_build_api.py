"""Owner-facing controls for Luna's staged, increasingly independent work."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from luna import core, self_build, mission_consent

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


class ExplicitMissionConsent(BaseModel):
    approve: bool


@router.get("/agent/self-build/model-consent")
def possible_model_consent():
    """No credentials or provider calls: display exactly what owner would allow."""
    snap = mission_consent.snapshot()
    return {
        "available_unverified": snap["available"],
        "provider": snap["provider"],
        "model": snap["model"],
        "transport": snap["transport"],
        "may_incur_charges": snap["billing_possible"],
        "max_model_calls": mission_consent.MAX_CALLS,
        "expires_minutes": mission_consent.EXPIRES_MINUTES,
        "only_existing_owner_missions": True,
        "future_missions_allowed": False,
        "code_installed": False,
    }


@router.get("/agent/self-build/consent/{mission_id}")
def mission_consent_status(mission_id: int):
    if mission_id < 1:
        raise HTTPException(400, "Invalid mission identifier")
    return mission_consent.info(core.DB_PATH, mission_id)


@router.post("/agent/self-build/authorize/{mission_id}")
def authorize_one_mission(mission_id: int, request: ExplicitMissionConsent):
    try:
        return mission_consent.authorize(core.DB_PATH, mission_id,
                                         approved=request.approve)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/agent/self-build/revoke/{mission_id}")
def revoke_one_mission(mission_id: int):
    try:
        return mission_consent.revoke(core.DB_PATH, mission_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


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
