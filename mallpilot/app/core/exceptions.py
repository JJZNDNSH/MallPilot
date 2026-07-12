class MallPilotError(Exception):
    # 业务错误编码。
    code: str = "mallpilot_error"

    # 初始化业务异常。
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ClarificationRequired(MallPilotError):
    # 需要用户补充信息。
    code = "clarification_required"
