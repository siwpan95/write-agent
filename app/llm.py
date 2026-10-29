"""大模型客户端：OpenAI 兼容协议（默认 DeepSeek），含 Mock 模式用于无 Key 演示/测试。

设计要点：
- 真实模式：经 `openai` SDK 访问 LLM_BASE_URL（任意 OpenAI 兼容端点）。
- Mock 模式（MOCK_LLM=true）：不联网，返回结构化占位响应，使全链路（含知识库检索与引用）
  无需密钥即可跑通；占位响应会明确标注「演示模式」，不会伪装成真实生成。
- 知识库问答的「逐条引用」由检索层（retriever）提供，与 LLM 文本解耦，更可靠。
"""
from __future__ import annotations

import time
from typing import Iterator, List, Dict, Any, Optional

from openai import OpenAI

from app.config import settings


class LLMError(RuntimeError):
    """LLM 调用相关错误。"""


class LLMClient:
    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    # ---------- 内部 ----------
    def _get_client(self) -> OpenAI:
        if settings.mock_llm:
            raise LLMError("当前为 Mock 模式，不创建真实客户端")
        if not settings.llm_api_key:
            raise LLMError(
                "未配置 LLM_API_KEY。请在 .env 中填写，或将 MOCK_LLM 设为 true 以演示。"
            )
        if self._client is None:
            self._client = OpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
            )
        return self._client

    # ---------- 公开接口 ----------
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> Any:
        """对话补全。

        非流式：返回完整文本字符串。
        流式：返回一个产出文本增量的生成器（Iterator[str]）。
        """
        if settings.mock_llm:
            return self._mock_chat(messages, stream=stream)

        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature if temperature is not None else settings.llm_temperature,
            stream=stream,
        )
        if stream:
            return self._stream_deltas(resp)
        return resp.choices[0].message.content or ""

    def _stream_deltas(self, resp) -> Iterator[str]:
        for chunk in resp:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def embed(self, texts: List[str]) -> List[List[float]]:
        """可选：稠密向量。仅在 KB_USE_EMBED=true 且配置了 embeddings 端点时调用。"""
        if not settings.embed_base_url or not settings.embed_api_key or not settings.embed_model:
            raise LLMError("未配置 embeddings（EMBED_BASE_URL/EMBED_API_KEY/EMBED_MODEL）")
        client = OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)
        resp = client.embeddings.create(model=settings.embed_model, input=texts)
        return [d.embedding for d in resp.data]

    # ---------- Mock ----------
    def _mock_chat(self, messages: List[Dict[str, str]], stream: bool = False):
        last_user = ""
        system = ""
        for m in messages:
            if m.get("role") == "user":
                last_user = m.get("content", "")
            elif m.get("role") == "system":
                system = m.get("content", "")
        # 依据系统提示里的任务标记生成不同占位内容
        task = "general"
        for tag in ("OUTLINE", "CHAPTER", "CONTINUE", "REWRITE", "STYLE", "KBQA"):
            if f"[MODE:{tag}]" in system:
                task = tag.lower()
                break

        text = self._mock_text(task, last_user, system)
        if stream:
            # 分片产出，模拟流式
            chunks = [text[i : i + 24] for i in range(0, len(text), 24)] or [text]
            return self._mock_stream(chunks)
        return text

    @staticmethod
    def _mock_stream(chunks: List[str]) -> Iterator[str]:
        for c in chunks:
            yield c
            time.sleep(0.01)

    @staticmethod
    def _mock_text(task: str, user: str, system: str) -> str:
        q = user.strip().replace("\n", " ")[:80]
        if task == "outline":
            return (
                "【演示模式·生成大纲】\n"
                "（未接入真实大模型，以下为占位结构，配置 LLM_API_KEY 后即为真实生成）\n\n"
                "第一卷 · 启幕\n"
                "  第01章 异界醒来 —— 主角在废墟中睁眼，记忆残缺。\n"
                "  第02章 残灯引路 —— 遇见第一位引路人，获得初始目标。\n"
                "  第03章 第一次抉择 —— 剧情分支点，决定后续阵营走向。\n"
                "（更多卷章依此展开……）"
            )
        if task == "chapter":
            return (
                "【演示模式·章节正文】\n"
                "（占位文本）夜色像浸了墨的棉布，沉沉压在城墙上。他握紧手中残破的符纸，\n"
                "听见风里传来不属于这个时代的钟声……\n"
                "（配置 LLM_API_KEY 后输出为真实创作内容。）"
            )
        if task == "continue":
            return "【演示模式·续写】……他向前迈了一步，脚下的石板发出古老的回响。（占位）"
        if task == "rewrite":
            return "【演示模式·改写】已按约束重排句式与节奏（占位），配置 Key 后为真实改写。"
        if task == "style":
            return "【演示模式·风格切换】已将叙述语调调整为所选风格（占位），配置 Key 后为真实输出。"
        if task == "kbqa":
            return (
                "【演示模式·知识库问答】\n"
                "（此处应由大模型依据下方「引用依据」中的资料作答；当前为占位，"
                "请配置 LLM_API_KEY 获得真实回答。引用依据由检索层提供，见消息下方。）"
            )
        return f"【演示模式】已收到消息：{q} ……（配置 LLM_API_KEY 后获得真实回复）"


# 单例
llm = LLMClient()
