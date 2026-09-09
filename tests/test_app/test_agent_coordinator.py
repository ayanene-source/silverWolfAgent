import threading
import time
import sys

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from module.agent.coordinator import AgentOperationCoordinator


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


class _FakeLog(QObject):
    taskFinished = Signal(int)

    def __init__(self):
        super().__init__()
        self.current_task = None
        self.logTextEdit = QPlainTextEdit()

    def isTaskRunning(self):
        return False


class _FakeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.logInterface = _FakeLog()


@pytest.mark.usefixtures("qapp")
def test_mutating_tool_waits_for_chat_confirmation(qapp):
    window = _FakeWindow()
    coordinator = AgentOperationCoordinator(window, window)
    called = []
    coordinator.approval_requested.connect(
        lambda request: coordinator.resolve_approval(request.request_id, True)
    )
    result_box = []
    worker = threading.Thread(
        target=lambda: result_box.append(
            coordinator.request_approval("test", "测试", "测试说明", lambda: called.append(True) or {"ok": True})
        )
    )
    worker.start()
    deadline = time.time() + 2
    while worker.is_alive() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    worker.join(timeout=0.1)
    assert not worker.is_alive()
    assert called == [True]
    assert result_box == [{"ok": True}]


@pytest.mark.usefixtures("qapp")
def test_agent_started_task_emits_a_completion_receipt(qapp):
    window = _FakeWindow()
    coordinator = AgentOperationCoordinator(window, window)
    events = []
    coordinator.operation_event.connect(events.append)
    operation = coordinator._create_operation("daily", "running")
    coordinator._active_operation_id = operation["operation_id"]
    window.logInterface.logTextEdit.setPlainText("任务日志最后一行")

    coordinator._on_task_finished(0)

    assert events[-1]["kind"] == "daily"
    assert events[-1]["status"] == "completed"
    assert events[-1]["exit_code"] == 0
    assert events[-1]["log_tail"] == ["任务日志最后一行"]
