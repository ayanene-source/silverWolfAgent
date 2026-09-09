# 银狼 Agent 学习版

这是一个用于学习 **Agent、工具调用与桌面应用集成** 的个人二次开发项目。

它以 [March7thAssistant](https://github.com/moesnow/March7thAssistant) 为运行框架，在其 PySide6 桌面应用中加入了一个以「银狼」为人设的 Agent 对话页面。原项目的游戏自动化功能、素材、工作流和相关文档并非本仓库作者原创或维护范围。

## 本次开发内容

- 银狼 Agent 对话界面，支持流式回复与会话历史。
- 使用 DeepSeek 模型，并通过 LangChain 组织模型与工具调用。
- 提供受限的工具能力：查看游戏状态、列出可用任务、启动游戏、执行每日实训、停止当前任务。
- 所有会产生实际操作的工具都必须在界面中由用户确认。
- 将 Agent 运行放在独立线程，避免请求模型时阻塞桌面界面。
- 提供 Agent 模块的基础单元测试与项目结构学习笔记。

## 当前边界

这是学习项目，不是独立的游戏自动化产品。Agent 只能调用白名单中的工具，不能执行任意 Python、文件或系统命令；目前也不会代替用户执行未开放的游戏任务。

使用自动化功能前，请自行了解游戏服务条款及可能的账号风险。

## 配置与启动

推荐使用 Python 3.12 及以上版本。在项目根目录安装依赖后启动桌面应用：

```powershell
python -m pip install -r requirements.txt
python app.py
```

首次使用 Agent 前，在环境变量中设置 DeepSeek API Key：

```powershell
$env:DEEPSEEK_API_KEY = "你的 API Key"
```

也可以在本地 `config.yaml` 中填写 `agent_api_key`。该文件属于个人配置，已被 Git 忽略，请勿提交真实密钥。

可在 `assets/config/config.example.yaml` 中调整以下示例项：

- `agent_model`：模型名称。
- `agent_temperature`：回复随机性。
- `agent_history_limit`：保留的对话轮数。
- `agent_base_url`：兼容接口地址；留空时使用默认地址。

## 学习入口

| 位置 | 说明 |
| --- | --- |
| `app/silver_wolf_interface.py` | Agent 聊天界面与确认卡片。 |
| `app/agent/chat_worker.py` | 将模型请求移出 GUI 主线程。 |
| `module/agent/runtime.py` | Agent 流式执行与工具调用处理。 |
| `module/agent/tools.py` | 可供模型调用的白名单工具。 |
| `module/agent/coordinator.py` | GUI 线程协调、用户确认和任务生命周期。 |
| `项目结构与学习指南.md` | 对原始框架的阅读路线和结构笔记。 |

## 致谢与许可

本仓库是 [moesnow/March7thAssistant](https://github.com/moesnow/March7thAssistant) 的衍生作品，并继续遵循 [GNU GPL v3.0](LICENSE)。原项目及其子模块拥有各自的作者、版权声明和许可证；使用、修改或再发布时，请保留这些声明并遵守对应许可。

本项目与米哈游、HoYoverse 及《崩坏：星穹铁道》无关联。
