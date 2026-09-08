"""兼容旧导入路径：app.domain.models.task -> report。"""
from app.domain.models.report import (
    AnalysisReport,
    AnalysisTask,
    AnalyzeTextRequest,
    StageInfo,
)

__all__ = [
    "AnalysisReport",
    "AnalysisTask",
    "AnalyzeTextRequest",
    "StageInfo",
]
