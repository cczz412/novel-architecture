"""只负责把登记过的本地零件复制进一次性试验工作区。"""

from .materialize import MaterializeError, materialize

__all__ = ["MaterializeError", "materialize"]
