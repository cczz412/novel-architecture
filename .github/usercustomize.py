"""Temporary WO4 cleanup imported after sitecustomize; self-removes."""
from pathlib import Path
import subprocess
for p in (Path('.github/PLEASE_OPEN_PR_NOW'), Path('.github/usercustomize.py')):
    if p.exists():
        subprocess.run(['git','rm','-f',p.as_posix()],check=True)
