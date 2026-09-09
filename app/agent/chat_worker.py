# 银狼对话线程桥：会话懒创建、模型构建、流式请求全部在工作线程完成，
# 主线程只收发信号，不接触 langchain，因此本模块顶部不 import module/agent。

from PySide6.QtCore import QThread, Signal


class ChatWorker(QThread):
    """一轮对话的异步执行单元（参照 app/card/pushsettingcard1.py 的短命线程惯例）"""

    chunk = Signal(str)     # 流式增量文本，逐段到达
    trace = Signal(str)     # Agent 决策、工具选择和工具结果（仅用于调试展示）
    finished = Signal(str)  # 完整回复（正常结束或主动中断后发出）
    error = Signal(str)     # 错误信息

    def __init__(self, session=None, user_text="", gateway=None, parent=None):
        super().__init__(parent)
        self.session = session      # 跨轮复用的会话对象；为 None 时在 run() 里懒创建
        self.user_text = user_text
        self.gateway = gateway

    def run(self):
        try:
            # 延迟导入：首次真正对话时才加载 langchain，且放在工作线程里避免卡界面
            from module.agent.llm import build_chat_model
            from module.agent.session import AgentSession
            from module.agent.runtime import AgentRuntime

            if self.session is None:
                from module.config import cfg
                limit = int(cfg.get_value("agent_history_limit", 10) or 10)
                self.session = AgentSession(llm=None, history_limit=max(1, limit))
                self.trace.emit(f"已创建会话：最多保留 {max(1, limit)} 轮历史")
            if self.session.llm is None:
                self.trace.emit("正在构建 DeepSeek 模型连接")
                self.session.llm = build_chat_model()

            if self.gateway is None:
                raise RuntimeError("Agent 工具网关未初始化")
            runtime = AgentRuntime(self.session.llm, self.gateway, self.trace.emit)
            parts = []
            for delta in runtime.stream_reply(self.session, self.user_text):
                if self.isInterruptionRequested():
                    # 页面销毁时主动中断；会话内部会回滚本轮上下文，下轮重试不会重复
                    break
                parts.append(delta)
                self.chunk.emit(delta)
            self.finished.emit("".join(parts))
        except Exception as e:
            self.trace.emit(f"Agent 错误：{e}")
            self.error.emit(str(e))
