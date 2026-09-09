import json

from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

from module.agent.runtime import AgentRuntime
from module.agent.session import AgentSession
from module.agent.tools import create_agent_tools


class FakeGateway:
    def to_json(self, payload):
        return json.dumps(payload, ensure_ascii=False)

    def record_tool_result(self, _tool_name, _payload):
        pass

    def get_game_status(self):
        return {"ok": True, "game_running": False, "task_running": False}

    def list_available_tasks(self):
        return [{"task_id": "daily", "agent_callable": True}]

    def start_game(self):
        return {"ok": False, "status": "cancelled"}

    def run_daily_task(self):
        return {"ok": False, "status": "cancelled"}

    def stop_current_task(self):
        return {"ok": True, "status": "idle"}


class ToolCapableFakeModel(FakeMessagesListChatModel):
    """The stock fake model intentionally has no tool binding implementation."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_tool_factory_exposes_only_allow_listed_tools():
    tools = create_agent_tools(FakeGateway())
    assert [tool.name for tool in tools] == [
        "get_game_status",
        "list_available_tasks",
        "start_game",
        "run_daily_task",
        "stop_current_task",
    ]
    assert tools[0].args_schema.model_json_schema()["properties"] == {}


def test_read_only_tools_return_json():
    tools = {tool.name: tool for tool in create_agent_tools(FakeGateway())}
    status = json.loads(tools["get_game_status"].invoke({}))
    tasks = json.loads(tools["list_available_tasks"].invoke({}))
    assert status["game_running"] is False
    assert tasks["tasks"][0]["agent_callable"] is True


def test_runtime_returns_model_text_and_updates_session():
    model = ToolCapableFakeModel(responses=[AIMessage(content="工具 MVP 已就绪")])
    session = AgentSession(llm=model)
    runtime = AgentRuntime(model, FakeGateway())
    assert "".join(runtime.stream_reply(session, "状态如何？")) == "工具 MVP 已就绪"
    assert session.messages[-1].content == "工具 MVP 已就绪"


def test_runtime_executes_a_tool_before_its_final_reply():
    model = ToolCapableFakeModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "get_game_status", "args": {}, "id": "status-1"}]),
        AIMessage(content="游戏当前未运行。"),
    ])
    session = AgentSession(llm=model)
    traces = []
    runtime = AgentRuntime(model, FakeGateway(), traces.append)
    assert "".join(runtime.stream_reply(session, "查询状态")) == "游戏当前未运行。"
    assert any("模型选择工具：get_game_status" in trace for trace in traces)
