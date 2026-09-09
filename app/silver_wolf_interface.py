# coding:utf-8
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from qfluentwidgets import (FluentIcon, InfoBar, InfoBarPosition, LineEdit,
                           PushButton, ScrollArea, isDarkTheme, qconfig)

from app.agent.chat_worker import ChatWorker
from module.agent.coordinator import AgentOperationCoordinator, ApprovalRequest
from module.config import cfg
from module.localization import tr

# ================= 素材 =================
# 把你准备的银狼头像放进这个目录，文件名任意，这里会按候选顺序找：
# 推荐命名：avatar.png（透明底正方形最佳，圆形裁切效果最好）
AVATAR_DIR = "./assets/app/images/silver_wolf"
AVATAR_CANDIDATES = (
    "avatar.png", "avatar.jpg", "head.png", "银狼.png", "SilverWolf.png",
)
AVATAR_FALLBACK = "./assets/app/images/SilverWolf.jpg"
AVATAR_SIZE = 36


class AgentTraceCard(QFrame):
    """One compact, expandable trace timeline for one Agent turn."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []
        self.setStyleSheet(
            "QFrame { background: rgba(86, 156, 214, 0.10); "
            "border: 1px solid rgba(86, 156, 214, 0.36); border-radius: 10px; }"
            "QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)
        header = QHBoxLayout()
        self.summary = QLabel("Agent 正在准备…", self)
        self.summary.setStyleSheet("font-size: 12px; color: #3b6f9e;")
        self.toggle = PushButton("详情", self)
        self.toggle.setFixedHeight(25)
        self.toggle.clicked.connect(self._toggle_details)
        header.addWidget(self.summary, 1)
        header.addWidget(self.toggle)
        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setMaximumBlockCount(80)
        self.details.setFixedHeight(130)
        self.details.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; "
            "font-family: Consolas, 'Microsoft YaHei'; font-size: 11px; }"
        )
        self.details.hide()
        layout.addLayout(header)
        layout.addWidget(self.details)

    def append_event(self, text: str):
        self._events.append(text)
        self.details.appendPlainText(text)
        self._set_summary(text)

    def finish(self, failed: bool = False):
        prefix = "执行失败" if failed else "本轮完成"
        self.summary.setText(f"{prefix} · {len(self._events)} 条运行事件")

    def _set_summary(self, text: str):
        if text.startswith("模型选择工具："):
            self.summary.setText(text.replace("模型选择工具：", "正在调用：", 1))
        elif text.startswith("工具等待确认："):
            self.summary.setText("等待你的确认")
        elif text.startswith("用户已确认："):
            self.summary.setText("已确认，正在执行工具")
        elif text.startswith("工具结果："):
            self.summary.setText(text.split(" → ", 1)[0].replace("工具结果：", "工具已返回：", 1))
        elif text.startswith("Agent 错误："):
            self.summary.setText("Agent 执行出错，点详情查看原因")
        else:
            self.summary.setText("Agent 正在思考…")

    def _toggle_details(self):
        visible = not self.details.isVisible()
        self.details.setVisible(visible)
        self.toggle.setText("收起" if visible else "详情")


def _resolve_avatar_path():
    """在 silver_wolf 目录里找头像；找不到就用项目自带图兜底"""
    for name in AVATAR_CANDIDATES:
        path = os.path.join(AVATAR_DIR, name)
        if os.path.exists(path):
            return path
    return AVATAR_FALLBACK if os.path.exists(AVATAR_FALLBACK) else None


def _round_pixmap(path, size):
    """把任意图片裁成圆形头像"""
    if not path or not os.path.exists(path):
        return QPixmap()
    src = QPixmap(path)
    if src.isNull():
        return QPixmap()
    src = src.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    x = (src.width() - size) // 2
    y = (src.height() - size) // 2
    src = src.copy(x, y, size, size)

    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return out


def _bubble_qss(sender: str) -> str:
    """按发送方与当前主题生成气泡样式"""
    if sender == "user":
        bg, fg = "#f18cb9", "#ffffff"          # 用户气泡：品牌粉
    elif sender == "trace":
        bg, fg = ("rgba(86, 156, 214, 0.20)", "#dbeeff") if isDarkTheme() else ("#edf5ff", "#3b5d7e")
    elif isDarkTheme():
        bg, fg = "rgba(255, 255, 255, 0.14)", "#ffffff"
    else:
        bg, fg = "#ffffff", "#1f1f1f"
    return (
        f"QFrame {{ background: {bg}; border-radius: 12px; }}"
        f"QLabel {{ color: {fg}; background: transparent; border: none; }}"
    )


class SilverWolfInterface(QWidget):
    """银狼页面：聊天式 agent 对话界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('silverWolfInterface')

        self._bubbles = []          # 已渲染的气泡 (frame, sender)，用于换主题/改宽度
        self._session = None        # AgentSession，首次发送时由 ChatWorker 懒创建
        self._worker = None         # 当前进行中的 ChatWorker
        self._stream_label = None   # 正在流式输出的气泡文本标签
        self._busy = False          # 请求进行中标记（防止连发）
        self._approval_cards = {}   # request_id -> (frame, confirm_btn, cancel_btn)
        self._active_trace_card = None
        self._avatar_pix = _round_pixmap(_resolve_avatar_path(), AVATAR_SIZE)

        self._build_ui()
        self._tool_gateway = AgentOperationCoordinator(self.window(), self)
        self._tool_gateway.approval_requested.connect(self._on_tool_approval_requested)
        self._tool_gateway.trace.connect(self._on_agent_trace)
        self._tool_gateway.operation_event.connect(self._on_operation_event)
        qconfig.themeChanged.connect(self._on_theme_changed)
        self.destroyed.connect(self._on_page_destroyed)

        # 开场问候
        self.add_assistant_message(tr("你好，我是银狼。有什么想让我帮忙的？"))
        QTimer.singleShot(0, self.input_edit.setFocus)

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(16, 16, 16, 16)
        self.vBoxLayout.setSpacing(8)

        # --- 顶部：头像 + 名字 + 状态 ---
        self.header = QWidget(self)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(4, 0, 4, 0)
        header_layout.setSpacing(8)

        self.avatar_label = QLabel(self.header)
        self.avatar_label.setPixmap(self._avatar_pix)
        self.avatar_label.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        self.avatar_label.setStyleSheet("background: transparent;")

        name_box = QVBoxLayout()
        name_box.setSpacing(0)
        self.name_label = QLabel(tr("银狼"), self.header)
        self.name_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.status_label = QLabel(tr("在线 · 待命"), self.header)
        self.status_label.setStyleSheet("font-size: 12px; color: #909399;")
        name_box.addWidget(self.name_label)
        name_box.addWidget(self.status_label)
        header_layout.addWidget(self.avatar_label)
        header_layout.addLayout(name_box)
        header_layout.addStretch(1)
        self.vBoxLayout.addWidget(self.header)

        # --- 中部：消息滚动区 ---
        self.chat_scroll = ScrollArea(self)
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")

        self.chat_view = QWidget(self.chat_scroll)
        self.messages_layout = QVBoxLayout(self.chat_view)
        self.messages_layout.setContentsMargins(8, 8, 8, 8)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch(1)     # 消息从底部往上顶
        self.chat_scroll.setWidget(self.chat_view)
        self.vBoxLayout.addWidget(self.chat_scroll, 1)

        # --- 底部：输入行 ---
        self.input_row = QWidget(self)
        input_layout = QHBoxLayout(self.input_row)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(8)
        self.input_edit = LineEdit(self.input_row)
        self.input_edit.setPlaceholderText(tr("说点什么…（Enter 发送）"))
        self.input_edit.setClearButtonEnabled(True)
        self.send_btn = PushButton(FluentIcon.SEND, tr("发送"), self.input_row)
        self.send_btn.setFixedHeight(32)
        input_layout.addWidget(self.input_edit, 1)
        input_layout.addWidget(self.send_btn)

        self.vBoxLayout.addWidget(self.input_row)

        # 信号
        self.send_btn.clicked.connect(self._on_send)
        self.input_edit.returnPressed.connect(self._on_send)

    # ---------------- 消息渲染 ----------------
    def add_user_message(self, text: str):
        self._add_message("user", text)

    def add_assistant_message(self, text: str):
        self._add_message("assistant", text)

    def _start_trace_turn(self):
        """Create one trace card per user turn instead of flooding the chat."""
        row = QWidget(self.chat_view)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        avatar = QLabel(row)
        avatar.setPixmap(self._avatar_pix)
        avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        avatar.setStyleSheet("background: transparent;")
        card = AgentTraceCard(row)
        card.setMaximumWidth(max(360, self.chat_view.width() * 72 // 100))
        row_layout.addWidget(avatar)
        row_layout.addWidget(card)
        row_layout.addStretch(1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._bubbles.append((card, "trace"))
        self._active_trace_card = card
        self._scroll_to_bottom()

    def _on_agent_trace(self, text: str):
        if self._active_trace_card is not None:
            self._active_trace_card.append_event(text)
            self._scroll_to_bottom()

    def _on_operation_event(self, event: dict):
        """Show asynchronous task results even after the Agent turn has ended."""
        labels = {"daily": tr("每日实训"), "start_game": tr("启动游戏"), "stop_task": tr("停止任务")}
        task_name = labels.get(event.get("kind"), event.get("kind", tr("任务")))
        event_type = event.get("event_type")
        status = event.get("status")
        if event_type == "started":
            self.add_assistant_message(
                tr("任务回执：{task}已启动，完成后我会主动通知你。").format(task=task_name)
            )
            return
        if status == "completed":
            self.add_assistant_message(
                tr("任务回执：{task}已成功完成。").format(task=task_name)
            )
        elif status == "failed":
            self._add_task_failure_card(task_name, event)
        elif status == "stopped":
            self.add_assistant_message(tr("任务回执：{task}已停止。").format(task=task_name))
        elif event.get("kind") == "stop_task":
            self.add_assistant_message(tr("任务回执：已请求停止当前自动化任务。"))

    def _add_task_failure_card(self, task_name: str, event: dict):
        """A deterministic failure receipt with an opt-in LLM diagnosis action."""
        row = QWidget(self.chat_view)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        avatar = QLabel(row)
        avatar.setPixmap(self._avatar_pix)
        avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        avatar.setStyleSheet("background: transparent;")
        card = QFrame(row)
        card.setMaximumWidth(max(360, self.chat_view.width() * 72 // 100))
        card.setStyleSheet(
            "QFrame { background: rgba(235, 87, 87, 0.12); "
            "border: 1px solid rgba(235, 87, 87, 0.56); border-radius: 12px; }"
            "QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel(tr("任务回执：{task}执行失败").format(task=task_name), card)
        title.setStyleSheet("font-weight: 600;")
        exit_code = event.get("exit_code")
        detail = tr("退出码：{code}。可让银狼根据任务日志分析原因。").format(
            code=exit_code if exit_code is not None else tr("未知")
        )
        layout.addWidget(title)
        layout.addWidget(QLabel(detail, card))
        analyze = PushButton(tr("让银狼分析失败原因"), card)
        analyze.clicked.connect(lambda: self._analyze_task_failure(task_name, event))
        layout.addWidget(analyze)
        row_layout.addWidget(avatar)
        row_layout.addWidget(card)
        row_layout.addStretch(1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._bubbles.append((card, "trace"))
        self._scroll_to_bottom()

    def _analyze_task_failure(self, task_name: str, event: dict):
        log_tail = "\n".join(event.get("log_tail") or [])
        model_text = (
            f"自动化任务“{task_name}”刚刚失败。退出码：{event.get('exit_code', '未知')}。\n"
            f"以下是最后日志，请分析最可能原因，并给出安全的排障步骤；"
            f"不要声称已修复，也不要执行任何工具。\n\n{log_tail}"
        )
        self._submit_message(tr("请分析刚才自动化任务失败的原因。"), model_text)

    def _add_message(self, sender: str, text: str) -> QLabel:
        """渲染一行气泡：assistant 左(带头像)，user 右；返回文本标签供流式更新"""
        row = QWidget(self.chat_view)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        bubble = QFrame(row)
        bubble.setMaximumWidth(max(300, self.chat_view.width() * 72 // 100))
        bubble.setStyleSheet(_bubble_qss(sender))
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        text_label = QLabel(text, bubble)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)   # 支持选中复制
        bubble_layout.addWidget(text_label)

        if sender == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            avatar = QLabel(row)
            avatar.setPixmap(self._avatar_pix)
            avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
            avatar.setStyleSheet("background: transparent;")
            row_layout.addWidget(avatar)
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)

        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1, row)
        self._bubbles.append((bubble, sender))
        self._scroll_to_bottom()
        return text_label

    def _add_approval_card(self, request: ApprovalRequest):
        """Render a human-in-the-loop card without blocking the Qt event loop."""
        row = QWidget(self.chat_view)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        avatar = QLabel(row)
        avatar.setPixmap(self._avatar_pix)
        avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        avatar.setStyleSheet("background: transparent;")

        card = QFrame(row)
        card.setMaximumWidth(max(360, self.chat_view.width() * 72 // 100))
        card.setStyleSheet(
            "QFrame { background: rgba(241, 140, 185, 0.16); "
            "border: 1px solid rgba(241, 140, 185, 0.58); border-radius: 12px; }"
            "QLabel { background: transparent; border: none; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        title = QLabel(f"需要确认：{request.title}", card)
        title.setStyleSheet("font-weight: 600;")
        detail = QLabel(request.description, card)
        detail.setWordWrap(True)
        detail.setStyleSheet("color: #909399;")
        buttons = QHBoxLayout()
        confirm = PushButton(tr("确认执行"), card)
        cancel = PushButton(tr("取消"), card)
        buttons.addWidget(confirm)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        card_layout.addWidget(title)
        card_layout.addWidget(detail)
        card_layout.addLayout(buttons)
        row_layout.addWidget(avatar)
        row_layout.addWidget(card)
        row_layout.addStretch(1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._approval_cards[request.request_id] = (card, confirm, cancel)

        confirm.clicked.connect(lambda: self._resolve_approval(request.request_id, True))
        cancel.clicked.connect(lambda: self._resolve_approval(request.request_id, False))
        QTimer.singleShot(60000, lambda: self._resolve_approval(request.request_id, False, "确认已超时"))
        self._scroll_to_bottom()

    def _on_tool_approval_requested(self, request: ApprovalRequest):
        self._add_approval_card(request)

    def _resolve_approval(self, request_id: str, approved: bool, reason: str = ""):
        card_data = self._approval_cards.pop(request_id, None)
        if card_data is not None:
            card, confirm, cancel = card_data
            confirm.setEnabled(False)
            cancel.setEnabled(False)
            card.setStyleSheet(
                "QFrame { background: rgba(80, 200, 120, 0.12); "
                "border: 1px solid rgba(80, 200, 120, 0.5); border-radius: 12px; }"
                "QLabel { background: transparent; border: none; }"
                if approved else
                "QFrame { background: rgba(144, 147, 153, 0.12); "
                "border: 1px solid rgba(144, 147, 153, 0.5); border-radius: 12px; }"
                "QLabel { background: transparent; border: none; }"
            )
            status = QLabel(tr("已确认，正在执行…") if approved else tr("已取消"), card)
            card.layout().insertWidget(2, status)
        self._tool_gateway.resolve_approval(request_id, approved, reason)

    def _scroll_to_bottom(self):
        def _go():
            bar = self.chat_scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        QTimer.singleShot(0, _go)

    # ---------------- 发送逻辑（LLM 流式对话） ----------------
    def _on_send(self):
        text = self.input_edit.text().strip()
        self._submit_message(text)

    def _submit_message(self, display_text: str, model_text: str | None = None):
        """Start a normal or system-assisted Agent turn with one visible user message."""
        if self._busy:
            return
        text = display_text.strip()
        if not text:
            return
        if not cfg.agent_enable:
            self._show_tip(
                tr("银狼 AI 未启用"),
                tr("请在 config.yaml 中设置 agent_enable: true 后重启应用。"))
            return
        self.add_user_message(text)
        self.input_edit.clear()
        self._start_trace_turn()
        self._set_busy(True)
        self._start_worker(model_text or text)

    def _start_worker(self, text: str):
        """每轮新建一个短命 worker；会话对象跨轮复用（首轮在工作线程里懒创建）"""
        worker = ChatWorker(self._session, text, self._tool_gateway, self)
        worker.chunk.connect(self._on_stream_chunk)
        worker.trace.connect(self._on_agent_trace)
        worker.finished.connect(self._on_stream_finished)
        worker.error.connect(self._on_stream_error)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _set_busy(self, busy: bool):
        """请求期间锁定输入，并在状态栏给出"思考中"反馈"""
        self._busy = busy
        self.input_edit.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.status_label.setText(tr("思考中…") if busy else tr("在线 · 待命"))

    def _on_stream_chunk(self, delta: str):
        # 首个分片到达时才插入空气泡，避免空回复留下多余气泡
        if self._stream_label is None:
            self._stream_label = self._add_message("assistant", "")
        label = self._stream_label
        label.setText(label.text() + delta)
        self._scroll_to_bottom()

    def _on_stream_finished(self, _full_text: str):
        # 流式文本已实时渲染，这里只回收状态；会话对象同步回页面供下轮复用
        self._sync_session_from_worker()
        self._stream_label = None
        self._worker = None
        if self._active_trace_card is not None:
            self._active_trace_card.finish()
            self._active_trace_card = None
        self._set_busy(False)

    def _on_stream_error(self, msg: str):
        self._sync_session_from_worker()
        self._stream_label = None
        self._worker = None
        if self._active_trace_card is not None:
            self._active_trace_card.finish(failed=True)
            self._active_trace_card = None
        self._set_busy(False)
        self._show_tip(tr("出错了"), msg)

    def _sync_session_from_worker(self):
        worker = self._worker
        if worker is not None and worker.session is not None:
            self._session = worker.session

    def _show_tip(self, title: str, content: str, level: str = "error"):
        """右上角通知条提示；level 可选 error / warning"""
        cls = InfoBar.error if level == "error" else InfoBar.warning
        cls(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=6000,
            parent=self.window(),
        )

    def _on_page_destroyed(self):
        # 页面销毁（应用退出）时若请求还在跑：请求中断并短暂等待线程收尾，避免 Qt 崩溃
        worker = self._worker
        if worker is not None:
            worker.requestInterruption()
            if worker.isRunning():
                worker.wait(15000)
            worker.deleteLater()
            self._worker = None
        for request_id in list(self._approval_cards):
            self._tool_gateway.resolve_approval(request_id, False, "页面已关闭")

    # ---------------- 适配 ----------------
    def resizeEvent(self, e):
        super().resizeEvent(e)
        max_w = max(300, self.chat_view.width() * 72 // 100)
        for bubble, _sender in self._bubbles:
            bubble.setMaximumWidth(max_w)

    def _on_theme_changed(self):
        """明暗主题切换后刷新气泡配色"""
        for bubble, sender in self._bubbles:
            if sender != "trace":
                bubble.setStyleSheet(_bubble_qss(sender))
