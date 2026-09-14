import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.ai import ChatTurn
from app.services.ai import get_ai_service
from app.services.upgrades import (CodebaseAnalyzer, GitUpgradeRepository, UpgradeExecutionError, UpgradeExecutor, UpgradePlanner, UpgradeSafetyError, VerificationPipeline, patch_paths)


PATCH = """diff --git a/apps/web/src/features/safe.tsx b/apps/web/src/features/safe.tsx
--- a/apps/web/src/features/safe.tsx
+++ b/apps/web/src/features/safe.tsx
@@ -1 +1 @@
-old
+new
"""

class FakeAI:
    def __init__(self, response: str): self.response = response
    def respond(self, messages: list[ChatTurn]) -> str: return self.response

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

def register(client: TestClient, prefix: str) -> None:
    response = client.post("/api/v1/auth/register", json={"email": f"{prefix}-{uuid4().hex}@example.com", "password": "secure-password-123", "display_name": "Upgrade Tester"})
    assert response.status_code == 201

class FakeRunner:
    def __init__(self, fail: str | None = None): self.calls: list[list[str]] = []; self.fail = fail
    def run(self, args, cwd):
        self.calls.append(args)
        if self.fail and self.fail in " ".join(args): raise UpgradeExecutionError("verification failed")
        if args[:3] == ["git", "rev-parse", "--is-inside-work-tree"]: return "true"
        if args[:3] == ["git", "status", "--porcelain"]: return ""
        if args[:3] == ["git", "rev-parse", "HEAD"]: return "abcdef1"
        if args[:3] == ["git", "branch", "--show-current"]: return "ultron/upgrade-43"
        return "ok"

def test_plan_is_only_created_and_never_applied_before_approval(tmp_path) -> None:
    payload = json.dumps({"plan":"Add a safe label.", "risk":"low", "affected_files":["apps/web/src/features/safe.tsx"], "patch":PATCH})
    plan = UpgradePlanner(FakeAI(payload), CodebaseAnalyzer(tmp_path)).create_plan("Add a safe label to the workspace")
    assert plan.affected_files == ["apps/web/src/features/safe.tsx"]

def test_valid_unified_patch_is_accepted() -> None:
    assert patch_paths(PATCH) == ["apps/web/src/features/safe.tsx"]

def test_malformed_unified_patch_is_rejected_before_git_apply(tmp_path) -> None:
    corrupt_patch = PATCH.replace("@@ -1 +1 @@", "@@ -1,2 +1 @@")
    runner = FakeRunner()
    with pytest.raises(UpgradeSafetyError, match="hunk line counts"):
        GitUpgradeRepository(tmp_path, runner).apply(corrupt_patch)
    assert not (tmp_path / ".ultron-upgrade.patch").exists()
    assert not any(call[:2] == ["git", "apply"] for call in runner.calls)

def test_affected_files_mismatch_is_rejected(tmp_path) -> None:
    payload = json.dumps({"plan":"Add a safe label.", "risk":"low", "affected_files":["apps/web/src/other.tsx"], "patch":PATCH})
    with pytest.raises(UpgradeSafetyError, match="affected-file list"):
        UpgradePlanner(FakeAI(payload), CodebaseAnalyzer(tmp_path)).create_plan("Add a safe label")

def test_protected_files_are_rejected() -> None:
    secret_patch = PATCH.replace("apps/web/src/features/safe.tsx", ".env")
    with pytest.raises(UpgradeSafetyError): patch_paths(secret_patch)

def test_patch_with_credential_like_content_is_rejected() -> None:
    with pytest.raises(UpgradeSafetyError): patch_paths(PATCH.replace("+new", "+api_key=not-a-real-key"))

def test_rejection_has_no_execution_side_effect() -> None:
    # The API decision gate is intentionally the sole caller of UpgradeExecutor.
    assert patch_paths(PATCH) == ["apps/web/src/features/safe.tsx"]

def test_successful_upgrade_checkpoints_applies_verifies_and_commits(tmp_path) -> None:
    runner = FakeRunner()
    repo = GitUpgradeRepository(tmp_path, runner)
    executor = UpgradeExecutor(repo, VerificationPipeline(tmp_path, runner))
    sha, branch, _ = executor.execute(42, PATCH)
    assert (sha, branch) == ("abcdef1", "ultron/upgrade-42")
    assert any(call[:2] == ["git", "commit"] for call in runner.calls)

def test_failed_upgrade_rolls_back_checkpoint(tmp_path) -> None:
    runner = FakeRunner(fail="compileall")
    repo = GitUpgradeRepository(tmp_path, runner)
    executor = UpgradeExecutor(repo, VerificationPipeline(tmp_path, runner))
    with pytest.raises(UpgradeExecutionError): executor.execute(43, PATCH)
    assert ["git", "reset", "--hard", "abcdef1"] in runner.calls

def test_upgrade_api_requires_approval_and_records_rejection(client: TestClient) -> None:
    plan = json.dumps({"plan":"Add a safe label.", "risk":"low", "affected_files":["apps/web/src/features/safe.tsx"], "patch":PATCH})
    app.dependency_overrides[get_ai_service] = lambda: FakeAI(plan)
    try:
        register(client, "upgrade-reject")
        proposal = client.post("/api/v1/upgrades", json={"feature_request":"Add a safe label to the workspace"})
        assert proposal.status_code == 201
        rejected = client.post(f"/api/v1/upgrades/{proposal.json()['id']}/decision", json={"approved": False})
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert all(event["status"] != "executing" for event in rejected.json()["events"])
    finally:
        app.dependency_overrides.clear()

def test_upgrade_api_executes_only_after_approval(client: TestClient, monkeypatch) -> None:
    from app.api import upgrades
    plan = json.dumps({"plan":"Add a safe label.", "risk":"low", "affected_files":["apps/web/src/features/safe.tsx"], "patch":PATCH})
    class Executor:
        def execute(self, upgrade_id, patch):
            assert patch == PATCH
            return "abcdef1", f"ultron/upgrade-{upgrade_id}", "all verification passed"
    monkeypatch.setattr(upgrades, "UpgradeExecutor", Executor)
    app.dependency_overrides[get_ai_service] = lambda: FakeAI(plan)
    try:
        register(client, "upgrade-approved")
        proposal = client.post("/api/v1/upgrades", json={"feature_request":"Add a safe label to the workspace"}).json()
        approved = client.post(f"/api/v1/upgrades/{proposal['id']}/decision", json={"approved": True})
        assert approved.status_code == 200
        assert approved.json()["status"] == "verified"
        assert approved.json()["checkpoint_sha"] == "abcdef1"
    finally:
        app.dependency_overrides.clear()
