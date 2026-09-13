import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from ..database import get_db
from ..models import Upgrade, UpgradeEvent, User
from ..schemas import RollbackIn, UpgradeDecisionIn, UpgradeRequestIn
from ..security import audit, current_user
from ..services.ai import ConversationAIService, get_ai_service
from ..services.upgrades import (GitUpgradeRepository, UpgradeExecutionError, UpgradeExecutor, UpgradePlanner, UpgradeSafetyError)

router = APIRouter(prefix="/upgrades", tags=["upgrades"])

def owned(db: DbSession, upgrade_id: int, user_id: int) -> Upgrade:
    upgrade = db.get(Upgrade, upgrade_id)
    if not upgrade or upgrade.user_id != user_id:
        raise HTTPException(404, "Upgrade not found")
    return upgrade

def event(db: DbSession, upgrade: Upgrade, status_value: str, message: str) -> None:
    db.add(UpgradeEvent(upgrade_id=upgrade.id, status=status_value, message=message[:4000]))

def serialize(db: DbSession, upgrade: Upgrade) -> dict:
    return {
        "id": upgrade.id, "feature_request": upgrade.feature_request, "plan": upgrade.plan,
        "affected_files": json.loads(upgrade.affected_files), "risk": upgrade.risk, "status": upgrade.status,
        "branch_name": upgrade.branch_name, "checkpoint_sha": upgrade.checkpoint_sha,
        "verification_log": upgrade.verification_log, "failure_reason": upgrade.failure_reason,
        "created_at": upgrade.created_at,
        "events": [{"status": item.status, "message": item.message, "created_at": item.created_at} for item in db.query(UpgradeEvent).filter_by(upgrade_id=upgrade.id).order_by(UpgradeEvent.created_at).all()],
    }

@router.get("")
def list_upgrades(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    return [serialize(db, item) for item in db.query(Upgrade).filter_by(user_id=user.id).order_by(Upgrade.created_at.desc()).all()]

@router.post("", status_code=status.HTTP_201_CREATED)
def propose_upgrade(payload: UpgradeRequestIn, user: User = Depends(current_user), db: DbSession = Depends(get_db), ai: ConversationAIService = Depends(get_ai_service)):
    try:
        plan = UpgradePlanner(ai).create_plan(payload.feature_request.strip())
    except UpgradeSafetyError as exc:
        raise HTTPException(422, str(exc))
    upgrade = Upgrade(user_id=user.id, feature_request=payload.feature_request.strip(), plan=plan.plan, affected_files=json.dumps(plan.affected_files), risk=plan.risk, patch=plan.patch)
    db.add(upgrade); db.commit(); db.refresh(upgrade)
    event(db, upgrade, "proposed", "Proposal created. No code has been changed; explicit approval is required.")
    db.commit(); audit(db, user.id, "Created self-upgrade proposal", result="pending approval", success=True)
    return serialize(db, upgrade)

@router.get("/{upgrade_id}")
def get_upgrade(upgrade_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    return serialize(db, owned(db, upgrade_id, user.id))

@router.post("/{upgrade_id}/decision")
def decide_upgrade(upgrade_id: int, payload: UpgradeDecisionIn, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    upgrade = owned(db, upgrade_id, user.id)
    if upgrade.status != "proposed":
        raise HTTPException(409, "Only a proposed upgrade can be decided.")
    if not payload.approved:
        upgrade.status = "rejected"; event(db, upgrade, "rejected", "User rejected the proposal. No code was changed.")
        db.commit(); audit(db, user.id, "Rejected self-upgrade", result=str(upgrade.id), decision="rejected")
        return serialize(db, upgrade)
    upgrade.status = "executing"; event(db, upgrade, "approved", "User explicitly approved this upgrade.")
    db.commit()
    try:
        checkpoint, branch, log = UpgradeExecutor().execute(upgrade.id, upgrade.patch or "")
        upgrade.status, upgrade.checkpoint_sha, upgrade.branch_name, upgrade.verification_log = "verified", checkpoint, branch, log
        event(db, upgrade, "verified", "Verification passed and the approved change was committed on its upgrade branch.")
        audit(db, user.id, "Executed self-upgrade", result=str(upgrade.id), decision="approved")
    except (UpgradeSafetyError, UpgradeExecutionError) as exc:
        upgrade.status, upgrade.failure_reason = "failed", str(exc)
        event(db, upgrade, "failed", "Upgrade failed safely; the checkpoint was restored when changes had been applied.")
        audit(db, user.id, "Self-upgrade failed safely", result=str(upgrade.id), decision="approved", success=False)
    db.commit()
    return serialize(db, upgrade)

@router.post("/{upgrade_id}/rollback")
def rollback_upgrade(upgrade_id: int, payload: RollbackIn, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    upgrade = owned(db, upgrade_id, user.id)
    if not payload.confirmed:
        raise HTTPException(422, "Rollback requires explicit confirmation.")
    if upgrade.status != "verified" or not upgrade.checkpoint_sha:
        raise HTTPException(409, "Only a verified upgrade with a checkpoint can be rolled back.")
    try:
        GitUpgradeRepository().rollback(upgrade.checkpoint_sha, json.loads(upgrade.affected_files))
    except (UpgradeSafetyError, UpgradeExecutionError) as exc:
        raise HTTPException(409, str(exc))
    upgrade.status = "rolled_back"; event(db, upgrade, "rolled_back", "User explicitly rolled the upgrade back to its Git checkpoint.")
    db.commit(); audit(db, user.id, "Rolled back self-upgrade", result=str(upgrade.id), decision="approved")
    return serialize(db, upgrade)
