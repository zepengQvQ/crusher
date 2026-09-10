"""错误码、任务状态、阶段状态。"""
from enum import Enum


class TaskStatus(str, Enum):
    """整次分析任务：排队 / 进行中 / 成功 / 失败。"""

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class StageStatus(str, Enum):
    """某一个分析步骤的状态。"""

    success = "success"
    partial = "partial"
    failed = "failed"
    not_applicable = "not_applicable"


class ErrorCode(str, Enum):
    INPUT_TOO_LONG = "INPUT_TOO_LONG"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_MODEL_JSON = "INVALID_MODEL_JSON"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    OUTPUT_VERIFICATION_FAILED = "OUTPUT_VERIFICATION_FAILED"
    RULE_FAILED = "RULE_FAILED"
    KNOWLEDGE_UNAVAILABLE = "KNOWLEDGE_UNAVAILABLE"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    FORBIDDEN_CLIENT_CONFIG = "FORBIDDEN_CLIENT_CONFIG"
    OCR_UNAVAILABLE = "OCR_UNAVAILABLE"
    DOCUMENT_PARSE_FAILED = "DOCUMENT_PARSE_FAILED"
    CALCULATION_INVALID = "CALCULATION_INVALID"
    INTENT_AMBIGUOUS = "INTENT_AMBIGUOUS"
    INPUT_INCOMPLETE = "INPUT_INCOMPLETE"
    CLARIFICATION_INVALID = "CLARIFICATION_INVALID"
    PRODUCT_CONFLICT = "PRODUCT_CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# 给用户看的短说明（网页展示用）
ERROR_USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INPUT_TOO_LONG: "文字太长了，请删短后再试",
    ErrorCode.MODEL_TIMEOUT: "模型调用失败：等待超时",
    ErrorCode.RATE_LIMITED: "模型调用失败：请求太频繁，请稍后再试",
    ErrorCode.INVALID_MODEL_JSON: "模型调用失败：返回内容格式不对",
    ErrorCode.MODEL_OUTPUT_INVALID: "模型输出无效，已阻止当作正常解释发布",
    ErrorCode.OUTPUT_VERIFICATION_FAILED: "模型解释未通过校验，仅展示程序已确认内容",
    ErrorCode.RULE_FAILED: "规则检查失败，请稍后重试",
    ErrorCode.KNOWLEDGE_UNAVAILABLE: "知识库暂时不可用",
    ErrorCode.TASK_NOT_FOUND: "找不到这个任务（可能服务刚重启过，请重新分析）",
    ErrorCode.FORBIDDEN_CLIENT_CONFIG: "网页不能传密钥或模型地址",
    ErrorCode.OCR_UNAVAILABLE: "当前模型不支持图片识别，扫描件 OCR 暂不可用",
    ErrorCode.DOCUMENT_PARSE_FAILED: "文件解析失败，请换文本 PDF 或直接粘贴文字",
    ErrorCode.CALCULATION_INVALID: "计算参数不合法或缺失，请确认后重试",
    ErrorCode.INTENT_AMBIGUOUS: "意图不明确，请确认要做的分析类型",
    ErrorCode.INPUT_INCOMPLETE: "输入还不完整，请先回答追问",
    ErrorCode.CLARIFICATION_INVALID: "追问答案不合法，请按选项或规范格式重新提交",
    ErrorCode.PRODUCT_CONFLICT: "产品类型存在冲突，请确认后继续",
    ErrorCode.INSUFFICIENT_EVIDENCE: "证据不足，无法给出确定结论",
    ErrorCode.UNSUPPORTED_REQUEST: "当前 Demo 不支持该类产品或请求",
    ErrorCode.INTERNAL_ERROR: "服务内部出错，请重试",
}


def user_message_for(code: ErrorCode, detail: str | None = None) -> str:
    base = ERROR_USER_MESSAGES.get(code, ERROR_USER_MESSAGES[ErrorCode.INTERNAL_ERROR])
    if detail and code == ErrorCode.INTERNAL_ERROR:
        return f"{base}（{detail}）"
    return base
