from pathlib import Path
import subprocess
for p in (Path('.github/wo4_last.txt'), Path('.github/wo4_trigger_cleanup.py')):
    if p.exists():
        subprocess.run(['git','rm','-f',p.as_posix()],check=True)
