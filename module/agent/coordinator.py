"""GUI-thread gateway for the Silver Wolf agent's controlled tools.

The LLM runs in a ``QThread``.  This module is the only bridge from that
thread to the Qt UI and the existing automation lifecycle.  It deliberately
does not expose arbitrary Python execution or arbitrary task IDs.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot


APPROVAL_TIMEOUT_SECONDS = 60


@dataclass
class MainThreadRequest:
    callback: Callable[[], Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None


@dataclass
class ApprovalRequest:
    request_id: str
    tool_name: str
    title: str
    description: str
    callback: Callable[[], dict[str, Any]]
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    resolved: bool = False


class AgentOperationCoordinator(QObject):
    """Owns Agent operations and marshals every GUI access to the UI thread."""

    approval_requested = Signal(object)
    main_thread_requested = Signal(object)
    trace = Signal(str)
    operation_event = Signal(object)

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self._lock = threading.RLock()
        self._approvals: dict[str, ApprovalRequest] = {}
        self._operations: dict[str, dict[str, Any]] = {}
        self._active_operation_id: str | None = None
        self._last_operation_id: str | None = None
        self._stop_requested_operation_id: str | None = None
        self.main_thread_requested.connect(self._run_main_thread_request)

        log_interface = getattr(main_window, "logInterface", None)
        if log_interface is not None:
            log_interface.taskFinished.connect(self._on_task_finished)

    def _on_main_thread(self) -> bool:
        return QThread.currentThread() == self.thread()

    def _call_on_main_thread(self, callback: Callable[[], Any]) -> Any:
        if self._on_main_thread():
            return callback()
        request = MainThreadRequest(callback=callback)
        self.main_thread_requested.emit(request)
        if not request.done.wait(APPROVAL_TIMEOUT_SECONDS):
            raise TimeoutError("等待 GUI 响应超时")
        if request.error:
            raise request.error
        return request.result

    @Slot(object)
    def _run_main_thread_request(self, request: MainThreadRequest):
        try:
            request.result = request.callback()
        except BaseException as error:
            request.error = error
        finally:
            request.done.set()

    def request_approval(
        self,
        tool_name: str,
        title: str,
        description: str,
        callback: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Request a chat-card approval and wait only in the agent worker."""
        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            tool_name=tool_name,
            title=title,
            description=description,
            callback=callback,
        )
        with self._lock:
            self._approvals[request.request_id] = request
        self.trace.emit(f"工具等待确认：{tool_name}（{title}）")
        self.approval_requested.emit(request)
        if not request.done.wait(APPROVAL_TIMEOUT_SECONDS):
            self.resolve_approval(request.request_id, False, "确认已超时")
        with self._lock:
            self._approvals.pop(request.request_id, None)
        return request.result or self._error("确认未完成")

    def resolve_approval(self, request_id: str, approved: bool, reason: str = ""):
        """Called by the chat UI. Safe to call from any Qt thread."""
        def resolve():
            with self._lock:
                request = self._approvals.get(request_id)
                if request is None or request.resolved:
                    return
                request.resolved = True
            if not approved:
                request.result = self._error(reason or "用户取消了本次操作", code="cancelled")
                self.trace.emit(f"工具已取消：{request.tool_name}（{reason or '用户取消'}）")
            else:
                self.trace.emit(f"用户已确认：{request.tool_name}")
                try:
                    request.result = request.callback()
                except Exception as error:
                    request.result = self._error(str(error))
            request.done.set()

        self._call_on_main_thread(resolve)

    @staticmethod
    def _error(message: str, code: str = "error") -> dict[str, Any]:
        return {"ok": False, "status": code, "message": message}

    def _create_operation(self, kind: str, status: str) -> dict[str, Any]:
        operation = {
            "operation_id": str(uuid.uuid4()),
            "kind": kind,
            "status": status,
            "started_at": time.time(),
            "finished_at": None,
            "message": "",
        }
        with self._lock:
            self._operations[operation["operation_id"]] = operation
            self._last_operation_id = operation["operation_id"]
        return operation

    def _emit_operation_event(self, operation: dict[str, Any], event_type: str, **extra):
        """Notify the Silver Wolf UI without requiring another model turn."""
        payload = dict(operation)
        payload.update(event_type=event_type, **extra)
        self.operation_event.emit(payload)

    def _finish_operation(self, operation_id: str, status: str, message: str, **extra):
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                return
            operation.update(status=status, message=message, finished_at=time.time())
            if self._active_operation_id == operation_id:
                self._active_operation_id = None
            event_operation = dict(operation)
        self._emit_operation_event(event_operation, "finished", **extra)

    def get_game_status(self) -> dict[str, Any]:
        def read_status():
            from module.game import get_game_controller

            log_interface = self.main_window.logInterface
            current_task = getattr(log_interface, "current_task", None)
            is_running = bool(log_interface.isTaskRunning())
            log_lines = log_interface.logTextEdit.toPlainText().splitlines()[-20:]
            try:
                game_running = bool(get_game_controller().is_game_running())
            except Exception as error:
                game_running = None
                game_error = str(error)
            else:
                game_error = None
            with self._lock:
                active = self._operations.get(self._active_operation_id) if self._active_operation_id else None
                last = self._operations.get(self._last_operation_id) if self._last_operation_id else None
            now = time.time()
            operation = active or last
            return {
                "ok": True,
                "game_running": game_running,
                "game_error": game_error,
                "current_task": current_task,
                "task_running": is_running,
                "operation_id": operation.get("operation_id") if operation else None,
                "operation_status": operation.get("status") if operation else None,
                "operation_elapsed_seconds": round(now - operation["started_at"], 1) if operation else None,
                "log_tail": log_lines,
            }

        return self._call_on_main_thread(read_status)

    def list_available_tasks(self) -> list[dict[str, Any]]:
        from utils.tasks import AVAILABLE_TASKS

        return [
            {"task_id": task_id, "name": task_name, "agent_callable": task_id == "daily"}
            for task_id, task_name in AVAILABLE_TASKS.items()
        ]

    def start_game(self) -> dict[str, Any]:
        def execute():
            from module.game import get_game_controller

            if get_game_controller().is_game_running():
                return {"ok": True, "status": "already_running", "message": "游戏已在运行"}
            operation = self._create_operation("start_game", "starting")
            self.main_window.startGame()
            launch_thread = getattr(self.main_window, "game_launch_thread", None)
            if launch_thread is not None:
                launch_thread.finished_signal.connect(
                    lambda result, op_id=operation["operation_id"]: self._on_game_launch_finished(op_id, result)
                )
            self._emit_operation_event(operation, "started")
            return {"ok": True, "status": "starting", "operation_id": operation["operation_id"], "message": "已请求启动游戏"}

        return self.request_approval("start_game", "启动游戏", "将启动《崩坏：星穹铁道》客户端。", execute)

    def _on_game_launch_finished(self, operation_id: str, result):
        status_name = getattr(result, "name", str(result))
        succeeded = status_name == "SUCCESS"
        self._finish_operation(
            operation_id,
            "completed" if succeeded else "failed",
            "游戏启动成功" if succeeded else f"游戏启动失败：{status_name}",
        )

    def run_daily_task(self) -> dict[str, Any]:
        def execute():
            log_interface = self.main_window.logInterface
            if log_interface.isTaskRunning():
                return self._error("已有任务正在运行，请先停止或等待其完成", code="busy")
            operation = self._create_operation("daily", "running")
            with self._lock:
                self._active_operation_id = operation["operation_id"]
            log_interface.startTask("daily")
            self._emit_operation_event(operation, "started")
            return {"ok": True, "status": "running", "operation_id": operation["operation_id"], "message": "每日实训已启动，可用 get_game_status 查询进度"}

        return self.request_approval("run_daily_task", "执行每日实训", "将启动每日实训自动化，可能执行游戏内操作。", execute)

    def stop_current_task(self) -> dict[str, Any]:
        def execute():
            log_interface = self.main_window.logInterface
            if not log_interface.isTaskRunning():
                return {"ok": True, "status": "idle", "message": "当前没有可停止的任务"}
            operation = self._create_operation("stop_task", "stopping")
            with self._lock:
                self._stop_requested_operation_id = self._active_operation_id
            log_interface.stopTask(user_initiated=True)
            self._finish_operation(operation["operation_id"], "requested", "已请求停止当前任务")
            return {"ok": True, "status": "stopping", "operation_id": operation["operation_id"], "message": "已请求停止当前任务"}

        return self.request_approval("stop_current_task", "停止当前任务", "将强制停止当前正在运行的自动化任务。", execute)

    @Slot(int)
    def _on_task_finished(self, exit_code: int):
        with self._lock:
            operation_id = self._active_operation_id
            stopped_by_request = operation_id is not None and operation_id == self._stop_requested_operation_id
            if stopped_by_request:
                self._stop_requested_operation_id = None
        if operation_id:
            log_interface = self.main_window.logInterface
            log_tail = log_interface.logTextEdit.toPlainText().splitlines()[-20:]
            self._finish_operation(
                operation_id,
                "stopped" if stopped_by_request else ("completed" if exit_code == 0 else "failed"),
                "任务已按请求停止" if stopped_by_request else ("任务完成" if exit_code == 0 else f"任务结束，退出码：{exit_code}"),
                exit_code=exit_code,
                log_tail=log_tail,
            )

    @staticmethod
    def to_json(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False)

    def record_tool_result(self, tool_name: str, payload: Any):
        """Expose a compact, safe-to-display result for the Agent trace."""
        rendered = self.to_json(payload)
        if len(rendered) > 700:
            rendered = rendered[:700] + "…（结果已截断）"
        self.trace.emit(f"工具结果：{tool_name} → {rendered}")
