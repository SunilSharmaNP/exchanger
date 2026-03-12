"""
Lightweight Updater Module
- Pulls code from UPSTREAM_REPO (config or env)
- Optionally updates Python packages
- Returns status messages for admin UI

Usage: call `await restart_bot()` from an admin handler.
"""
import os
import asyncio
import shlex
from subprocess import run
from importlib import import_module
from os import environ


def get_config():
    cfg = {}
    try:
        conf = import_module("config")
        cfg = {k: v for k, v in vars(conf).items() if not k.startswith("__")}
    except ModuleNotFoundError:
        pass
    # override with environment
    for k in ("UPSTREAM_REPO", "UPSTREAM_BRANCH", "UPDATE_PKGS"):
        if k in environ:
            cfg[k] = environ[k]
    return cfg


def run_shell(cmd, check=False, shell=False):
    """Run a shell command synchronously and return (rc, out, err)"""
    try:
        if isinstance(cmd, str) and not shell:
            cmd = shlex.split(cmd)
        p = run(cmd, capture_output=True, text=True, shell=shell)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 1, "", str(e)


async def update_from_upstream(cfg):
    repo = cfg.get("UPSTREAM_REPO", "").strip()
    branch = cfg.get("UPSTREAM_BRANCH", "main").strip()
    if not repo:
        return False, "UPSTREAM_REPO not configured"

    # ensure git is present
    rc, _, _ = run_shell(["which", "git"])  # returns 0 if found
    if rc != 0:
        return False, "git is not installed on the host"

    # perform safe pull: fetch remote and reset
    cmds = []
    # initialize if no .git
    if not os.path.exists(".git"):
        cmds.append("git init -q")
        cmds.append("git remote add origin " + repo)
    else:
        # update remote url
        cmds.append("git remote remove origin || true")
        cmds.append("git remote add origin " + repo)

    cmds.append("git fetch origin --depth=1")
    cmds.append(f"git reset --hard origin/{branch}")

    # run combined
    full = " && ".join(cmds)
    rc, out, err = await asyncio.to_thread(run_shell, full, False, True)
    if rc == 0:
        return True, "Updated from upstream successfully"
    return False, f"Git update failed: {err or out}"


async def update_packages(cfg):
    up = cfg.get("UPDATE_PKGS", "True")
    if isinstance(up, str):
        up = up.lower() == "true"
    if not up:
        return True, "Package update disabled"

    # try pip install -U -r requirements.txt
    rc, out, err = await asyncio.to_thread(run_shell, "pip install -U -r requirements.txt", False, True)
    if rc == 0:
        return True, "Packages updated"
    return False, f"Package update failed: {err or out}"


async def restart_bot():
    """Orchestrate update steps and return (success:bool, message:str)

    Note: Caller may restart process after this returns True.
    """
    cfg = get_config()
    # Step 1: update code
    ok, msg = await update_from_upstream(cfg)
    if not ok:
        return False, msg

    # Step 2: update packages
    ok2, msg2 = await update_packages(cfg)
    # We continue even if packages fail, but report
    if not ok2:
        return True, "Code updated; packages update failed: " + msg2

    return True, "Update completed successfully"
