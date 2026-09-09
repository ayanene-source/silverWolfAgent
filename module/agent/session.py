# 银狼对话会话：维护 system 人设 + 多轮上下文，封装流式/非流式回复。
# 纯 Python 无 Qt 依赖，方便 pytest 单测与将来 CLI 复用。

from typing import Iterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from module.agent.persona import PERSONA_SYSTEM_PROMPT


class AgentSession:
    """一次对话会话：负责上下文消息列表的维护与截断"""

    def __init__(self, llm=None, system_prompt: str = None, history_limit: int = 10):
        """llm 可延迟到首次对话前注入（由工作线程构建），避免 GUI 主线程加载 langchain"""
        if history_limit < 1:
            raise ValueError("history_limit 必须 >= 1")
        self.llm = llm
        self.history_limit = history_limit
        self.messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt or PERSONA_SYSTEM_PROMPT)
        ]

    @staticmethod
    def system_prompt_text() -> str:
        """The current system prompt is passed separately to ``create_agent``."""
        return PERSONA_SYSTEM_PROMPT

    def reset(self):
        """清空历史，只保留系统人设（用于"新对话"）"""
        self.messages = [self.messages[0]]

    def _trim_history(self):
        """只保留系统提示 + 最近 history_limit 轮对话（一轮 = 一问一答两条）"""
        keep = 2 * self.history_limit
        if len(self.messages) - 1 > keep:
            self.messages = [self.messages[0]] + self.messages[-keep:]

    def stream_reply(self, user_text: str) -> Iterator[str]:
        """追加用户消息并流式返回模型回答的增量文本；
        流式中断或抛错时回滚本轮用户消息，避免重试时上下文重复"""
        if self.llm is None:
            raise RuntimeError("会话模型未初始化，请先构建并注入 ChatDeepSeek")
        self.messages.append(HumanMessage(content=user_text))
        parts = []
        try:
            for chunk in self.llm.stream(self.messages):
                content = getattr(chunk, "content", "")
                if not isinstance(content, str) or not content:
                    continue
                parts.append(content)
                yield content
        except BaseException:
            if self.messages and isinstance(self.messages[-1], HumanMessage):
                self.messages.pop()
            raise
        # 流式正常结束才把完整回答记入历史，再按轮数截断
        self.messages.append(AIMessage(content="".join(parts)))
        self._trim_history()

    def chat(self, user_text: str) -> str:
        """非流式入口，供测试与将来 CLI 使用"""
        return "".join(self.stream_reply(user_text))
