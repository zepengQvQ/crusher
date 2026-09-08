"""Mock LLM 网关（P0-02 不发起真实模型请求）。"""


class MockLlmGateway:
    async def complete(self, prompt: str) -> str:
        return f"[mock] ignored prompt length={len(prompt)}"
