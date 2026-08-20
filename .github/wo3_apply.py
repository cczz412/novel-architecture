#!/usr/bin/env python3
"""Final lint wrapper for the temporary WO3 materializer.

The previous fixed wrapper already produces the complete WO3 artifacts. This
last layer removes one unused ``copy`` import from the generated read-only
checker before materialization, without changing its behavior or write set.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
PREVIOUS_WRAPPER_COMMIT = "7cc55c37f3dffb1364c5abc85d2b9e34552d0479"
PREVIOUS = subprocess.check_output(
    ["git", "show", f"{PREVIOUS_WRAPPER_COMMIT}:.github/wo3_apply.py"],
    text=True,
)
RUN_MARKER = 'NAMESPACE["main"]()'
if not PREVIOUS.rstrip().endswith(RUN_MARKER):
    raise SystemExit("previous WO3 wrapper no longer ends with the expected run marker")
PREVIOUS = PREVIOUS[: PREVIOUS.rfind(RUN_MARKER)]
WRAPPER_NAMESPACE: dict[str, object] = {
    "__name__": "wo3_previous_wrapper",
    "__file__": str(THIS_FILE),
}
exec(compile(PREVIOUS, "wo3_previous_wrapper.py", "exec"), WRAPPER_NAMESPACE)
NAMESPACE = WRAPPER_NAMESPACE["NAMESPACE"]
CHECKER_SOURCE = NAMESPACE["CHECKER_SOURCE"]
if CHECKER_SOURCE.count("import copy\n") != 1:
    raise SystemExit("generated checker does not contain exactly one unused copy import")
NAMESPACE["CHECKER_SOURCE"] = CHECKER_SOURCE.replace("import copy\n", "", 1)
NAMESPACE["main"]()
