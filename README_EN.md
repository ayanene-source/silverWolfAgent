# Silver Wolf Agent Learning Edition

[简体中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md)

This is a personal derivative project for learning **agents, tool calling, and desktop-app integration**.

It uses [March7thAssistant](https://github.com/moesnow/March7thAssistant) as its application framework and adds an Agent chat page with a Silver Wolf persona to its PySide6 desktop app. The original project's game automation, assets, workflows, and related documentation are not original work of, or maintained by, this repository's author.

## What was added here

- A Silver Wolf Agent chat UI with streamed replies and chat history.
- DeepSeek model access, with LangChain used to structure model and tool calls.
- Restricted tools for checking game status, listing available tasks, starting the game, running the daily task, and stopping the current task.
- An explicit in-app user confirmation before every tool that performs an action.
- A dedicated Agent thread so model requests do not block the desktop UI.
- Basic Agent-module tests and project-structure learning notes.

## Scope and safety

This is a learning project, not a standalone game-automation product. The Agent may only invoke allow-listed tools; it cannot run arbitrary Python, access arbitrary files, or execute system commands. It also cannot run game tasks that have not been explicitly exposed.

Before using automation features, review the game's terms of service and understand the potential account risks yourself.

## Setup and run

Python 3.12 or newer is recommended. From the project root, install dependencies and start the desktop app:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Before using the Agent, set your DeepSeek API key as an environment variable:

```powershell
$env:DEEPSEEK_API_KEY = "your API key"
```

Alternatively, set `agent_api_key` in the local `config.yaml`. This personal configuration file is ignored by Git; never commit a real key.

The following example settings are available in `assets/config/config.example.yaml`:

- `agent_model`: Model name.
- `agent_temperature`: Response randomness.
- `agent_history_limit`: Number of conversation turns to retain.
- `agent_base_url`: Compatible API endpoint; leave empty to use the default endpoint.

## Where to learn

| Location | Purpose |
| --- | --- |
| `app/silver_wolf_interface.py` | Agent chat UI and confirmation cards. |
| `app/agent/chat_worker.py` | Moves model requests off the GUI thread. |
| `module/agent/runtime.py` | Agent streaming execution and tool-call handling. |
| `module/agent/tools.py` | Allow-listed tools exposed to the model. |
| `module/agent/coordinator.py` | GUI-thread coordination, user confirmation, and task lifecycle. |
| `项目结构与学习指南.md` | Reading path and notes for the original framework. |

## Attribution and license

This repository is a derivative work of [moesnow/March7thAssistant](https://github.com/moesnow/March7thAssistant) and remains licensed under [GNU GPL v3.0](LICENSE). The original project and its submodules retain their own authors, copyright notices, and licenses. Preserve those notices and comply with the applicable licenses when using, modifying, or redistributing this work.

This project is not affiliated with miHoYo, HoYoverse, or *Honkai: Star Rail*.
