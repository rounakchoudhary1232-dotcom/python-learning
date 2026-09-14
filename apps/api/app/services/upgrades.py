"""Approval-gated self-upgrade primitives.

This module deliberately has no general shell or filesystem execution API.  It
only accepts a validated unified diff, invokes a small fixed Git command
allowlist, and runs a fixed verification pipeline from the repository root.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from .ai import ChatTurn, ConversationAIService

MAX_PATCH_BYTES = 250_000
MIN_GENERATED_PATCH_BYTES = 64
SAFE_PREFIXES = ("apps/api/app/", "apps/api/tests/", "apps/web/src/", "apps/web/tests/", "docs/")
PROTECTED_PATHS = {
    ".env", ".env.example", "apps/api/app/config.py", "apps/api/app/database.py",
    "apps/api/app/migrations.py", "apps/api/app/models.py", "apps/api/app/security.py", "apps/api/app/main.py",
    "apps/api/app/api/mvp.py", "apps/api/app/api/upgrades.py", "apps/api/app/services/upgrades.py",
}
BLOCKED_PARTS = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv"}
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


class UpgradeSafetyError(RuntimeError):
    pass


class UpgradeExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpgradePlan:
    plan: str
    affected_files: list[str]
    risk: str
    patch: str


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def redact_text(value: str) -> str:
    # Defense in depth: source snippets and provider failures must never expose secrets.
    return re.sub(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[^\s,]+", r"\1=[REDACTED]", value)


def validate_upgrade_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    candidate = PurePosixPath(normalized)
    if not normalized or normalized.startswith("/") or ".." in candidate.parts:
        raise UpgradeSafetyError("Upgrade paths must be relative to the project root.")
    if any(part in BLOCKED_PARTS for part in candidate.parts):
        raise UpgradeSafetyError("The proposed patch touches a blocked directory.")
    if normalized in PROTECTED_PATHS or normalized.startswith(".env"):
        raise UpgradeSafetyError("The proposed patch touches a protected security or configuration file.")
    if not normalized.startswith(SAFE_PREFIXES):
        raise UpgradeSafetyError("The proposed patch is outside the controlled upgrade allowlist.")
    return normalized


def validate_unified_diff(patch: str) -> None:
    """Reject structurally corrupt diffs before they reach ``git apply``.

    Git's parser accepts a broad patch format, but a generated patch must at
    least have complete file headers and hunks whose stated line counts match
    their bodies.  This catches the common LLM failure mode (bad hunk counts)
    without changing the repository's existing apply/checkpoint safeguards.
    """
    if not patch.endswith("\n"):
        raise UpgradeSafetyError("Malformed unified diff: patch is truncated (missing final newline).")
    lines = patch.splitlines()
    position = 0
    files = 0

    while position < len(lines):
        header = lines[position].split()
        if len(header) != 4 or header[:2] != ["diff", "--git"] or not header[2].startswith("a/") or not header[3].startswith("b/"):
            raise UpgradeSafetyError("Malformed unified diff: each file must begin with a valid Git diff header.")
        old_path, new_path = header[2][2:], header[3][2:]
        if not old_path or not new_path:
            raise UpgradeSafetyError("Malformed unified diff: Git diff header has an empty path.")
        if old_path != new_path:
            raise UpgradeSafetyError("Malformed unified diff: renames and copies are not supported.")
        files += 1
        position += 1

        saw_old, saw_new, saw_hunk = False, False, False
        while position < len(lines) and not lines[position].startswith("diff --git "):
            line = lines[position]
            if line.startswith("--- "):
                if saw_old or saw_new:
                    raise UpgradeSafetyError("Malformed unified diff: duplicate file headers.")
                if line[4:].split("\t", 1)[0] not in {f"a/{old_path}", "/dev/null"}:
                    raise UpgradeSafetyError("Malformed unified diff: old file header does not match Git diff header.")
                saw_old = True
            elif line.startswith("+++ "):
                if not saw_old or saw_new:
                    raise UpgradeSafetyError("Malformed unified diff: invalid file-header order.")
                if line[4:].split("\t", 1)[0] not in {f"b/{new_path}", "/dev/null"}:
                    raise UpgradeSafetyError("Malformed unified diff: new file header does not match Git diff header.")
                if line[4:].split("\t", 1)[0] == "/dev/null" and lines[position - 1][4:].split("\t", 1)[0] == "/dev/null":
                    raise UpgradeSafetyError("Malformed unified diff: both file headers cannot be /dev/null.")
                saw_new = True
            elif line.startswith("@@"):
                if not (saw_old and saw_new):
                    raise UpgradeSafetyError("Malformed unified diff: hunk is missing file headers.")
                match = HUNK_HEADER.fullmatch(line)
                if not match:
                    raise UpgradeSafetyError("Malformed unified diff: invalid hunk header.")
                old_expected = int(match.group(2) or 1)
                new_expected = int(match.group(4) or 1)
                if old_expected == new_expected == 0:
                    raise UpgradeSafetyError("Malformed unified diff: empty hunk.")
                old_actual = new_actual = 0
                previous_was_content = False
                position += 1
                while position < len(lines) and not lines[position].startswith(("diff --git ", "@@")):
                    body_line = lines[position]
                    if body_line == "\\ No newline at end of file":
                        if not previous_was_content:
                            raise UpgradeSafetyError("Malformed unified diff: misplaced no-newline marker.")
                        previous_was_content = False
                        position += 1
                        continue
                    if not body_line.startswith((" ", "+", "-")):
                        raise UpgradeSafetyError("Malformed unified diff: invalid hunk line.")
                    if body_line[0] in " -":
                        old_actual += 1
                    if body_line[0] in " +":
                        new_actual += 1
                    previous_was_content = True
                    position += 1
                if (old_actual, new_actual) != (old_expected, new_expected):
                    raise UpgradeSafetyError(
                        "Malformed unified diff: hunk line counts do not match its header."
                    )
                saw_hunk = True
                continue
            elif saw_old or saw_new:
                raise UpgradeSafetyError("Malformed unified diff: unexpected content between file headers and hunks.")
            elif not line.startswith(("index ", "new file mode ", "deleted file mode ", "old mode ", "new mode ")):
                raise UpgradeSafetyError("Malformed unified diff: unexpected Git file metadata.")
            position += 1

        if not (saw_old and saw_new and saw_hunk):
            raise UpgradeSafetyError("Malformed unified diff: each file requires headers and at least one hunk.")

    if not files:
        raise UpgradeSafetyError("Malformed unified diff: no file changes were found.")


def patch_paths(patch: str) -> list[str]:
    if not patch or len(patch.encode()) > MAX_PATCH_BYTES:
        raise UpgradeSafetyError("A non-empty, reasonably sized patch is required.")
    if re.search(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]", patch):
        raise UpgradeSafetyError("The proposed patch appears to contain a credential and was rejected.")
    validate_unified_diff(patch)
    paths: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) != 4:
                raise UpgradeSafetyError("Malformed Git patch header.")
            for raw in parts[2:]:
                validate_upgrade_path(raw[2:] if raw.startswith(("a/", "b/")) else raw)
        elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            raise UpgradeSafetyError("Renames and copies are not supported by the controlled editor.")
        if line.startswith("+++ "):
            raw = line[4:].split("\t", 1)[0]
            if raw == "/dev/null":
                continue
            if raw.startswith("b/"):
                raw = raw[2:]
            paths.append(validate_upgrade_path(raw))
        elif line.startswith("--- "):
            raw = line[4:].split("\t", 1)[0]
            if raw != "/dev/null":
                if raw.startswith("a/"):
                    raw = raw[2:]
                validate_upgrade_path(raw)
    if not paths or "@@" not in patch:
        raise UpgradeSafetyError("Only standard unified patches with at least one hunk are allowed.")
    return list(dict.fromkeys(paths))


def needs_patch_regeneration(patch: str) -> bool:
    """Identify incomplete model output that merits one constrained retry."""
    return not patch.strip() or len(patch.encode()) < MIN_GENERATED_PATCH_BYTES or not patch.endswith("\n")


class CodebaseAnalyzer:
    def __init__(self, root: Path | None = None):
        self.root = root or project_root()

    def inventory(self, limit: int = 80) -> list[str]:
        files: list[str] = []
        for prefix in SAFE_PREFIXES:
            folder = self.root / prefix
            if not folder.exists():
                continue
            for candidate in folder.rglob("*"):
                if not candidate.is_file() or any(part in BLOCKED_PARTS for part in candidate.parts):
                    continue
                relative = candidate.relative_to(self.root).as_posix()
                if relative in PROTECTED_PATHS or candidate.stat().st_size > 40_000:
                    continue
                files.append(relative)
                if len(files) >= limit:
                    return files
        return files

    def context(self) -> str:
        # File inventory permits useful planning without uploading source or secrets.
        return "\n".join(self.inventory())

    def refreshed_file_context(self, paths: list[str]) -> str:
        """Read the current allowlisted files immediately before patch regeneration."""
        contents: list[str] = []
        for path in paths:
            normalized = validate_upgrade_path(path)
            candidate = self.root / normalized
            if not candidate.is_file() or candidate.stat().st_size > 40_000:
                continue
            contents.append(f"--- {normalized}\n{candidate.read_text(encoding='utf-8')}")
        return "\n".join(contents)


class UpgradePlanner:
    def __init__(self, ai: ConversationAIService, analyzer: CodebaseAnalyzer | None = None):
        self.ai, self.analyzer = ai, analyzer or CodebaseAnalyzer()

    def create_plan(self, feature_request: str) -> UpgradePlan:
        prompt = f"""You are ULTRON's constrained self-upgrade planner. Analyze the feature request and repository inventory below. Return ONLY JSON with string keys plan, risk, patch and array affected_files. risk must be low, medium, or high. patch must be a deterministic Git unified diff: for every changed file emit exactly `diff --git a/<path> b/<path>`, `--- a/<path>` (or `/dev/null`), and `+++ b/<path>` (or `/dev/null`) before its hunks. Every hunk must use `@@ -old_start,old_count +new_start,new_count @@` and its old/new counts must exactly match its `-`/`+`/context lines. Do not emit prose, markdown fences, ellipses, binary changes, renames, copies, or omitted/truncated hunks. End the patch with a newline. Never modify .env, auth, security, database/migration, upgrade-engine, or API routing files. Never include secrets. If no safe patch is possible, use an empty patch and explain why in plan.\n\nFeature request:\n{feature_request}\n\nAllowed repository inventory:\n{self.analyzer.context()}"""
        raw = self.ai.respond([ChatTurn(role="user", content=prompt)])
        plan = self._parse_plan(raw)
        if plan.risk not in {"low", "medium", "high"}:
            raise UpgradeSafetyError("The upgrade plan has an invalid risk level.")
        regenerated = False
        try:
            actual_paths = patch_paths(plan.patch)
        except UpgradeSafetyError as exc:
            if not needs_patch_regeneration(plan.patch) and not str(exc).startswith("Malformed unified diff:"):
                raise
            plan = self._parse_plan(self._regenerate(feature_request, plan, exc))
            regenerated = True
            if plan.risk not in {"low", "medium", "high"}:
                raise UpgradeSafetyError("The upgrade plan has an invalid risk level.")
            actual_paths = patch_paths(plan.patch)
        if set(plan.affected_files) != set(actual_paths):
            raise UpgradeSafetyError("The affected-file list does not match the proposed patch.")
        apply_error = self._patch_apply_error(plan.patch)
        if apply_error and "patch does not apply" in apply_error.lower():
            if regenerated:
                raise UpgradeSafetyError("The regenerated patch does not apply to the current working tree.")
            plan = self._parse_plan(self._regenerate(feature_request, plan, UpgradeSafetyError(apply_error)))
            if plan.risk not in {"low", "medium", "high"}:
                raise UpgradeSafetyError("The upgrade plan has an invalid risk level.")
            actual_paths = patch_paths(plan.patch)
            if set(plan.affected_files) != set(actual_paths):
                raise UpgradeSafetyError("The affected-file list does not match the proposed patch.")
            apply_error = self._patch_apply_error(plan.patch)
            if apply_error:
                raise UpgradeSafetyError("The regenerated patch does not apply to the current working tree.")
        return plan

    def _parse_plan(self, raw: str) -> UpgradePlan:
        try:
            content = raw.strip().removeprefix("```json").removesuffix("```").strip()
            value = json.loads(content)
            return UpgradePlan(
                plan=redact_text(str(value["plan"]))[:8000],
                affected_files=[validate_upgrade_path(str(p)) for p in value["affected_files"]],
                risk=str(value.get("risk", "medium")).lower(),
                patch=str(value.get("patch", "")),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise UpgradeSafetyError("The AI provider returned an invalid upgrade plan.") from exc

    def _regenerate(self, feature_request: str, plan: UpgradePlan, error: UpgradeSafetyError) -> str:
        refreshed_context = self.analyzer.refreshed_file_context(plan.affected_files)
        prompt = f"""Regenerate ULTRON's upgrade plan because its patch was incomplete, malformed, or stale. Return ONLY JSON with string keys plan, risk, patch and array affected_files. Implement the original request using the refreshed file contents below. The patch must make the requested change, touch exactly affected_files, and be a complete deterministic Git unified diff: each file needs `diff --git a/<path> b/<path>`, `---`, `+++`, valid counted `@@` hunks, and a final newline. Do not emit prose, markdown fences, placeholders, ellipses, binary changes, renames, or copies. Do not modify protected files or include credentials. The previous patch was rejected: {redact_text(str(error))}.\n\nOriginal request:\n{feature_request}\n\nPrevious affected files:\n{json.dumps(plan.affected_files)}\n\nRefreshed affected-file contents:\n{refreshed_context}\n\nAllowed repository inventory:\n{self.analyzer.context()}"""
        return self.ai.respond([ChatTurn(role="user", content=prompt)])

    def _patch_apply_error(self, patch: str) -> str | None:
        """Return a read-only Git applicability failure, or None when unavailable/passing."""
        try:
            # A new-file patch has no current file to compare; Git validates it
            # at execution.  Check stale context only for existing targets.
            if any(not (self.analyzer.root / path).is_file() for path in patch_paths(patch)):
                return None
            inside_tree = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"], cwd=self.analyzer.root,
                shell=False, capture_output=True, text=True, timeout=15, check=False,
            )
            if inside_tree.returncode or inside_tree.stdout.strip() != "true":
                return None
            checked = subprocess.run(
                ["git", "apply", "--check", "-"], cwd=self.analyzer.root, input=patch,
                shell=False, capture_output=True, text=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if checked.returncode:
            return (checked.stderr or checked.stdout or "git apply --check failed").strip()
        return None


class CommandRunner(Protocol):
    def run(self, args: list[str], cwd: Path) -> str: ...


class FixedCommandRunner:
    """Runs arguments directly, never through a shell."""
    def run(self, args: list[str], cwd: Path) -> str:
        try:
            completed = subprocess.run(args, cwd=cwd, shell=False, capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpgradeExecutionError("A controlled upgrade command could not be started or timed out.") from exc
        if completed.returncode:
            raise UpgradeExecutionError(redact_text((completed.stderr or completed.stdout or "Controlled command failed.")[-2000:]))
        return (completed.stdout or "").strip()


class GitUpgradeRepository:
    def __init__(self, root: Path | None = None, runner: CommandRunner | None = None):
        self.root, self.runner = root or project_root(), runner or FixedCommandRunner()

    def checkpoint(self, upgrade_id: int) -> tuple[str, str]:
        if self.runner.run(["git", "rev-parse", "--is-inside-work-tree"], self.root) != "true":
            raise UpgradeExecutionError("Self-upgrades require a Git working tree.")
        if self.runner.run(["git", "status", "--porcelain"], self.root):
            raise UpgradeExecutionError("Self-upgrades require a clean Git working tree.")
        sha = self.runner.run(["git", "rev-parse", "HEAD"], self.root)
        branch = f"ultron/upgrade-{upgrade_id}"
        self.runner.run(["git", "switch", "-c", branch], self.root)
        return sha, branch

    def apply(self, patch: str) -> list[str]:
        paths = patch_paths(patch)
        patch_file = self.root / ".ultron-upgrade.patch"
        patch_file.write_text(patch, encoding="utf-8")
        try:
            self.runner.run(["git", "apply", "--check", str(patch_file)], self.root)
            self.runner.run(["git", "apply", "--whitespace=nowarn", str(patch_file)], self.root)
        finally:
            patch_file.unlink(missing_ok=True)
        return paths

    def commit(self, upgrade_id: int, paths: list[str]) -> None:
        self.runner.run(["git", "add", "--", *paths], self.root)
        self.runner.run(["git", "commit", "-m", f"ULTRON approved upgrade {upgrade_id}"], self.root)

    def rollback(self, checkpoint_sha: str, paths: list[str]) -> None:
        if not re.fullmatch(r"[0-9a-f]{7,64}", checkpoint_sha):
            raise UpgradeSafetyError("Invalid checkpoint reference.")
        for path in paths:
            validate_upgrade_path(path)
        branch = self.runner.run(["git", "branch", "--show-current"], self.root)
        if not re.fullmatch(r"ultron/upgrade-\d+", branch):
            raise UpgradeSafetyError("Rollback is only allowed from its ULTRON upgrade branch.")
        self.runner.run(["git", "reset", "--hard", checkpoint_sha], self.root)
        # New files created by an approved patch are removed only at their validated paths.
        for path in paths:
            candidate = self.root / path
            if candidate.exists() and not self._tracked(path):
                candidate.unlink()

    def _tracked(self, path: str) -> bool:
        try:
            self.runner.run(["git", "ls-files", "--error-unmatch", "--", path], self.root)
            return True
        except UpgradeExecutionError:
            return False


class VerificationPipeline:
    def __init__(self, root: Path | None = None, runner: CommandRunner | None = None):
        self.root, self.runner = root or project_root(), runner or FixedCommandRunner()

    def run(self) -> str:
        commands = [
            ([sys.executable, "-m", "compileall", "-q", "apps/api/app"], self.root),
            ([sys.executable, "-m", "pytest", "-q", "apps/api/tests"], self.root),
            (["npm", "run", "lint"], self.root / "apps/web"),
        ]
        outputs: list[str] = []
        for command, cwd in commands:
            outputs.append(self.runner.run(command, cwd)[-1000:])
        return "\n".join(outputs)


class UpgradeExecutor:
    def __init__(self, repository: GitUpgradeRepository | None = None, verifier: VerificationPipeline | None = None):
        self.repository, self.verifier = repository or GitUpgradeRepository(), verifier or VerificationPipeline()

    def execute(self, upgrade_id: int, patch: str) -> tuple[str, str, str]:
        sha, branch = self.repository.checkpoint(upgrade_id)
        paths = self.repository.apply(patch)
        try:
            log = self.verifier.run()
            self.repository.commit(upgrade_id, paths)
            return sha, branch, log
        except Exception as exc:
            self.repository.rollback(sha, paths)
            raise UpgradeExecutionError(redact_text(str(exc))) from exc
