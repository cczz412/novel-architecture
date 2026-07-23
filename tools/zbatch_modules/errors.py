"""运行器与模块共享的错误接口。"""


class ZBatchError(RuntimeError):
    """与旧运行器同名、同基类、同错误消息的独立错误接口。"""
