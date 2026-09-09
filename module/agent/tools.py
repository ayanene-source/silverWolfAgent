"""The allow-listed LangChain tools exposed to the Silver Wolf agent."""

from langchain_core.tools import tool

from module.agent.coordinator import AgentOperationCoordinator


def create_agent_tools(gateway: AgentOperationCoordinator):
    """Build tools bound to one GUI session's controlled gateway."""

    def result(tool_name: str, payload) -> str:
        gateway.record_tool_result(tool_name, payload)
        return gateway.to_json(payload)

    @tool
    def get_game_status() -> str:
        """查询游戏是否运行、当前自动化任务、Agent 操作状态和最近任务日志。无副作用。"""
        return result("get_game_status", gateway.get_game_status())

    @tool
    def list_available_tasks() -> str:
        """列出应用内任务，并标记哪些任务当前允许 Agent 调用。无副作用。"""
        return result("list_available_tasks", {"ok": True, "tasks": gateway.list_available_tasks()})

    @tool
    def start_game() -> str:
        """请求启动游戏。必须先经过用户在聊天界面中的明确确认。"""
        return result("start_game", gateway.start_game())

    @tool
    def run_daily_task() -> str:
        """请求执行每日实训（现有 daily 任务）。必须先经过用户明确确认。"""
        return result("run_daily_task", gateway.run_daily_task())

    @tool
    def stop_current_task() -> str:
        """请求停止当前正在运行的自动化任务。必须先经过用户明确确认。"""
        return result("stop_current_task", gateway.stop_current_task())

    return [get_game_status, list_available_tasks, start_game, run_daily_task, stop_current_task]
