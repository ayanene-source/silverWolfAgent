# 銀狼 Agent 学習版

[简体中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md)

これは、**Agent、ツール呼び出し、デスクトップアプリ統合**を学ぶための個人二次開発プロジェクトです。

[March7thAssistant](https://github.com/moesnow/March7thAssistant) をアプリケーション基盤として利用し、その PySide6 デスクトップアプリに「銀狼」をペルソナとする Agent チャット画面を追加しています。元プロジェクトのゲーム自動化機能、アセット、ワークフロー、および関連ドキュメントは、このリポジトリの作者によるオリジナル作品・保守対象ではありません。

## このリポジトリで追加したもの

- ストリーミング応答と会話履歴に対応した銀狼 Agent チャット UI。
- DeepSeek モデルの接続と、LangChain によるモデル・ツール呼び出しの構成。
- ゲーム状態の確認、利用可能なタスクの一覧、ゲーム起動、デイリータスク実行、実行中タスク停止に限定したツール。
- 実際の操作を行うすべてのツールに対する、アプリ内での明示的なユーザー確認。
- モデルリクエストによってデスクトップ UI をブロックしないための専用 Agent スレッド。
- Agent モジュールの基本テストと、プロジェクト構造の学習メモ。

## 範囲と安全性

これは学習プロジェクトであり、単体のゲーム自動化製品ではありません。Agent が呼び出せるのは許可リストにあるツールのみで、任意の Python 実行、任意ファイルへのアクセス、システムコマンドの実行はできません。また、明示的に公開されていないゲームタスクを実行することもありません。

自動化機能を使用する前に、ゲームの利用規約とアカウントに対する潜在的なリスクを各自で確認してください。

## セットアップと起動

Python 3.12 以降を推奨します。プロジェクトのルートで依存関係をインストールし、デスクトップアプリを起動します。

```powershell
python -m pip install -r requirements.txt
python app.py
```

Agent を使用する前に、DeepSeek API キーを環境変数に設定します。

```powershell
$env:DEEPSEEK_API_KEY = "あなたの API Key"
```

または、ローカルの `config.yaml` に `agent_api_key` を設定できます。この個人設定ファイルは Git の管理対象外です。実際のキーは絶対にコミットしないでください。

`assets/config/config.example.yaml` では、次のサンプル設定を調整できます。

- `agent_model`：モデル名。
- `agent_temperature`：応答のランダム性。
- `agent_history_limit`：保持する会話ターン数。
- `agent_base_url`：互換 API エンドポイント。空欄の場合は既定のエンドポイントを使用します。

## 学習の入口

| 場所 | 役割 |
| --- | --- |
| `app/silver_wolf_interface.py` | Agent チャット UI と確認カード。 |
| `app/agent/chat_worker.py` | モデルリクエストを GUI スレッドから分離。 |
| `module/agent/runtime.py` | Agent のストリーミング実行とツール呼び出し処理。 |
| `module/agent/tools.py` | モデルに公開する許可リストのツール。 |
| `module/agent/coordinator.py` | GUI スレッドの調整、ユーザー確認、タスクのライフサイクル。 |
| `项目结构与学习指南.md` | 元のフレームワークの読解ルートと学習メモ。 |

## 謝辞とライセンス

このリポジトリは [moesnow/March7thAssistant](https://github.com/moesnow/March7thAssistant) の派生作品であり、[GNU GPL v3.0](LICENSE) の下で配布されます。元プロジェクトとそのサブモジュールには、それぞれの著者、著作権表示、ライセンスがあります。利用、改変、再配布の際は、これらの表示を保持し、該当するライセンスに従ってください。

本プロジェクトは、miHoYo、HoYoverse、および『崩壊：スターレイル』とは一切関係ありません。
