"""Temporary WO4 marker cleanup; removed before the final PR commit."""

from pathlib import Path
import subprocess

for _path in (Path(".github/wo4_pr_marker.md"), Path("usercustomize.py")):
    if _path.exists():
        subprocess.run(["git", "rm", "-f", _path.as_posix()], check=True)
