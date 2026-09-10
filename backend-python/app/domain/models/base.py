"""领域模型公共基类。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """默认拒绝多余字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
