"""LangChain agent runtime used by the Silver Wolf chat worker."""

from __future__ import annotations

import json
from typing import Callable, Iterator

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from module.agent.coordinator import AgentOperationCoordinator
from module.agent.session import AgentSession
from module.agent.tools import create_agent_tools


class AgentRuntime:
    """Runs the LangChain tool loop while keeping the existing session history."""

    def __init__(self, llm, gateway: AgentOperationCoordinator, trace_callback: Callable[[str], None] | None = None):
        self.agent = create_agent(
            model=llm,
            tools=create_agent_tools(gateway),
            system_prompt=AgentSession.system_prompt_text(),
            name="silver_wolf_agent",
        )
        self.trace_callback = trace_callback

    def _trace(self, message: str):
        if self.trace_callback:
            self.trace_callback(message)

    def stream_reply(self, session: AgentSession, user_text: str) -> Iterator[str]:
        history_count = max(0, len(session.messages) - 1)
        self._trace(f"上下文已载入：系统提示词 + {history_count} 条历史消息；本轮工具：5 个")
        session.messages.append(HumanMessage(content=user_text))
        parts: list[str] = []
        try:
            # ``messages`` mode produces token-sized AIMessageChunk values while
            # create_agent handles all tool-call / ToolMessage rounds internally.
            for message, _metadata in self.agent.stream(
                {"messages": session.messages[1:]}, stream_mode="messages"
            ):
                # Providers normally yield AIMessageChunk tokens, while test
                # doubles and a few integrations yield a complete AIMessage.
                if not isinstance(message, (AIMessageChunk, AIMessage)):
                    continue
                if message.tool_calls:
                    for call in message.tool_calls:
                        name = call.get("name", "unknown")
                        args = json.dumps(call.get("args", {}), ensure_ascii=False)
                        self._trace(f"模型选择工具：{name}({args})")
                    continue
                content = message.content
                if isinstance(content, str) and content:
                    parts.append(content)
                    yield content
            session.messages.append(AIMessage(content="".join(parts)))
            session._trim_history()
        except BaseException:
            self._trace("Agent 本轮执行异常，已回滚未完成的用户消息")
            if session.messages and isinstance(session.messages[-1], HumanMessage):
                session.messages.pop()
            raise
