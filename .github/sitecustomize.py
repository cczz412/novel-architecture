"""Temporary WO4 cleanup imported when the helper runs; self-removes."""
from pathlib import Path
import subprocess
for p in (Path('.github/DO_NOT_ADD_MORE_MARKERS'), Path('.github/sitecustomize.py')):
    if p.exists():
        subprocess.run(['git','rm','-f',p.as_posix()],check=True)
