"""OCR 相关错误。"""


class OcrUnavailableError(Exception):
    """当前端点不支持图片输入或未配置视觉能力。"""


class OcrFailedError(Exception):
    """单页 OCR 失败。"""
