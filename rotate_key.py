"""Project-root key-rotation entry point.

In a Docker deployment, the default target is the running backend container so
rotation operates on the same persistent /app/data volume used by the app.
Use --local to force host-process rotation.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent / "backend"


def _docker_backend_running() -> bool:
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "-q", "backend"],
            cwd=Path(__file__).resolve().parent,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(result.returncode == 0 and result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def _run_docker(args: list[str]) -> int:
    command = [
        "docker", "compose", "exec", "-T", "backend",
        "python", "/app/rotate_keys.py", *args,
    ]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parent, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate Reporting Tool application keys safely.")
    parser.add_argument("--encryption", action="store_true")
    parser.add_argument("--secret", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--local", action="store_true", help="Force rotation in the host Python environment.")
    args = parser.parse_args()

    if not (args.encryption or args.secret or args.all):
        parser.error("Specify --encryption, --secret, or --all.")

    rotation_args = [flag for flag, enabled in (
        ("--encryption", args.encryption),
        ("--secret", args.secret),
        ("--all", args.all),
    ) if enabled]

    # Docker is the deployed application target when its backend is running.
    # This keeps the root convenience command on the same persistent data/keyring.
    if not args.local and _docker_backend_running():
        return _run_docker(rotation_args)

    sys.path.insert(0, str(BACKEND))
    from rotate_keys import main as backend_main  # noqa: E402

    return backend_main(rotation_args)


if __name__ == "__main__":
    raise SystemExit(main())
