"""Mock LLM 网关（默认演示模式不发起真实模型请求）。"""


class MockLlmGateway:
    async def complete(self, prompt: str) -> str:
        return f"[mock] ignored prompt length={len(prompt)}"
