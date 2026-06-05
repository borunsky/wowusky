"""Git-based profile sync (#66).

Uses a local git repository as the sync target for a full profile bundle
(see :mod:`wowusky.core.profile_bundle`). ``push`` writes the bundle, commits
and pushes; ``pull`` fetches the latest and returns the bundle for the caller
to apply. Works with any git remote (GitHub, Gitea, a bare repo on disk).

Everything degrades gracefully when git is unavailable or the sync repo is
not configured — the status reports the condition rather than raising.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

BUNDLE_FILENAME = "wowusky-profile.json"


def _git_available() -> bool:
    return shutil.which("git") is not None


def get_repo_path() -> str:
    from wowusky.core import config as _config

    return os.path.expanduser(_config.get("sync_repo_path", "") or "")


def set_repo_path(path: str) -> None:
    from wowusky.core import config as _config

    _config.set_key("sync_repo_path", (path or "").strip())


def _git(repo: str, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def status() -> dict:
    """Report whether sync is usable and what is on disk."""
    repo = get_repo_path()
    if not _git_available():
        return {"available": False, "configured": bool(repo), "repo_path": repo}
    if not repo:
        return {"available": True, "configured": False, "repo_path": ""}
    is_repo = os.path.isdir(os.path.join(repo, ".git"))
    has_bundle = os.path.isfile(os.path.join(repo, BUNDLE_FILENAME))
    return {
        "available": True,
        "configured": True,
        "repo_path": repo,
        "is_repo": is_repo,
        "has_bundle": has_bundle,
    }


def push(profile_id=None, log=print) -> dict:
    """Write the current profile bundle into the repo, commit and push."""
    from wowusky.core import profile_bundle as _pb

    repo = get_repo_path()
    if not _git_available():
        return {"ok": False, "error": "git is not installed"}
    if not repo:
        return {"ok": False, "error": "no sync repo configured"}
    if not os.path.isdir(os.path.join(repo, ".git")):
        return {"ok": False, "error": f"not a git repository: {repo}"}

    bundle = _pb.export_profile_bundle(profile_id)
    target = os.path.join(repo, BUNDLE_FILENAME)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
    log(f"wrote {BUNDLE_FILENAME} ({len(bundle.get('addons', []))} addons)")

    _git(repo, "add", BUNDLE_FILENAME)
    rc, out = _git(repo, "diff", "--cached", "--quiet")
    if rc == 0:
        return {"ok": True, "pushed": False, "message": "nothing changed"}
    rc, out = _git(repo, "commit", "-m", f"wowusky sync: {bundle['profile'].get('name', '')}")
    if rc != 0:
        return {"ok": False, "error": out or "commit failed"}
    rc, out = _git(repo, "push")
    if rc != 0:
        # A commit was made locally even if push failed (e.g. no remote).
        return {"ok": False, "pushed": False, "error": out or "push failed"}
    log("pushed to remote")
    return {"ok": True, "pushed": True}


def pull(log=print) -> dict:
    """Pull the latest bundle from the repo and return it for applying."""
    repo = get_repo_path()
    if not _git_available():
        return {"ok": False, "error": "git is not installed"}
    if not repo:
        return {"ok": False, "error": "no sync repo configured"}
    if not os.path.isdir(os.path.join(repo, ".git")):
        return {"ok": False, "error": f"not a git repository: {repo}"}

    rc, out = _git(repo, "pull", "--ff-only")
    # A failed pull (e.g. no remote / offline) is non-fatal — fall back to the
    # bundle already on disk, but surface the message.
    pull_msg = out
    target = os.path.join(repo, BUNDLE_FILENAME)
    if not os.path.isfile(target):
        return {"ok": False, "error": f"no {BUNDLE_FILENAME} in the sync repo"}
    try:
        with open(target, encoding="utf-8") as fh:
            bundle = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"could not read bundle: {exc}"}
    log(pull_msg or "using local bundle")
    return {"ok": True, "bundle": bundle, "pull_message": pull_msg}
