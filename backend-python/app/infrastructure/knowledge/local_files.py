"""知识库适配器占位（P0-02 不实现真实匹配）。"""


class LocalFileKnowledgeRepository:
    def ping(self) -> bool:
        return True
