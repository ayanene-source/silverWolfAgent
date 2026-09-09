# 银狼对话的 GUI 线程桥目录：worker 只依赖 PySide6，不直接 import langchain，
# 保证主界面启动与切换页面零加载开销。
