# Eclusa アーキテクチャ

> コントリビューターおよび上級ユーザー向けのシステムアーキテクチャ文書です。ユーザー向けドキュメントは[機能リファレンス](FEATURES.md)または[ユーザーガイド](USER-GUIDE.md)をご覧ください。

---

## 目次

- [システム概要](#システム概要)
- [設計原則](#設計原則)
- [コンポーネントアーキテクチャ](#コンポーネントアーキテクチャ)
- [エージェントモデル](#エージェントモデル)
- [データフロー](#データフロー)
- [ファイルシステムレイアウト](#ファイルシステムレイアウト)
- [インストーラーアーキテクチャ](#インストーラーアーキテクチャ)
- [フックシステム](#フックシステム)
- [CLIツールレイヤー](#cliツールレイヤー)
- [ランタイム抽象化](#ランタイム抽象化)

---

## システム概要

Eclusaは、ユーザーとAIコーディングエージェント（Claude Code、Gemini CLI、OpenCode、Codex、Copilot、Antigravity）の間に位置する**メタプロンプティングフレームワーク**です。以下の機能を提供します：

1. **コンテキストエンジニアリング** — タスクごとにAIが必要とするすべてを提供する構造化アーティファクト
2. **マルチエージェントオーケストレーション** — 専門エージェントをフレッシュなコンテキストウィンドウで起動する軽量オーケストレーター
3. **仕様駆動開発** — 要件 → 調査 → 計画 → 実行 → 検証のパイプライン
4. **状態管理** — セッションやコンテキストリセットをまたいだ永続的なプロジェクトメモリ

```
┌──────────────────────────────────────────────────────┐
│                      USER                            │
│            /eclusa:command [args]                        │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│              COMMAND LAYER                            │
│   commands/eclusa/*.md — Prompt-based command files      │
│   (Claude Code custom commands / Codex skills)        │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│              WORKFLOW LAYER                           │
│   eclusa/workflows/*.md — Orchestration logic  │
│   (Reads references, spawns agents, manages state)    │
└──────┬──────────────┬─────────────────┬──────────────┘
       │              │                 │
┌──────▼──────┐ ┌─────▼─────┐ ┌────────▼───────┐
│  AGENT      │ │  AGENT    │ │  AGENT         │
│  (fresh     │ │  (fresh   │ │  (fresh        │
│   context)  │ │   context)│ │   context)     │
└──────┬──────┘ └─────┬─────┘ └────────┬───────┘
       │              │                 │
┌──────▼──────────────▼─────────────────▼──────────────┐
│              CLI TOOLS LAYER                          │
│   eclusa/bin/eclusa-tools.cjs                     │
│   (State, config, phase, roadmap, verify, templates)  │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│              FILE SYSTEM (.eclusa/)                 │
│   PROJECT.md | REQUIREMENTS.md | ROADMAP.md          │
│   STATE.md | config.json | phases/ | research/       │
└──────────────────────────────────────────────────────┘
```

---

## 設計原則

### 1. エージェントごとにフレッシュなコンテキスト

オーケストレーターが起動するすべてのエージェントは、クリーンなコンテキストウィンドウ（最大200Kトークン）を取得します。これにより、AIがコンテキストウィンドウに蓄積された会話で埋め尽くされることによる品質低下（コンテキストの劣化）が排除されます。

### 2. 軽量オーケストレーター

ワークフローファイル（`eclusa/workflows/*.md`）は重い処理を行いません。以下の役割に徹します：
- `eclusa-tools.cjs init <workflow>` でコンテキストを読み込む
- 焦点を絞ったプロンプトで専門エージェントを起動する
- 結果を収集し、次のステップにルーティングする
- ステップ間で状態を更新する

### 3. ファイルベースの状態管理

すべての状態は `.eclusa/` 内に人間が読めるMarkdownとJSONとして保存されます。データベースもサーバーも外部依存もありません。これにより：
- コンテキストリセット（`/clear`）後も状態が維持される
- 人間とエージェントの両方が状態を確認できる
- チームでの可視性のためにgitにコミットできる

### 4. 未設定 = 有効

ワークフローの機能フラグは **未設定 = 有効** のパターンに従います。`config.json` にキーが存在しない場合、デフォルトで `true` になります。ユーザーは機能を明示的に無効化します。デフォルトを有効化する操作は不要です。

### 5. 多層防御

複数のレイヤーで一般的な障害モードを防止します：
- 実行前に計画が検証される（plan-checkerエージェント）
- 実行時にタスクごとにアトミックなコミットが生成される
- 実行後の検証でフェーズ目標との整合性を確認する
- UATが最終ゲートとして人間による検証を提供する

---

## コンポーネントアーキテクチャ

### コマンド（`commands/eclusa/*.md`）

ユーザー向けのエントリーポイントです。各ファイルにはYAMLフロントマター（name、description、allowed-tools）とワークフローをブートストラップするプロンプト本文が含まれています。コマンドは以下の形式でインストールされます：
- **Claude Code:** カスタムスラッシュコマンド（`/eclusa:command-name`）
- **OpenCode:** スラッシュコマンド（`/eclusa-command-name`）
- **Codex:** スキル（`$eclusa-command-name`）
- **Copilot:** スラッシュコマンド（`/eclusa:command-name`）
- **Antigravity:** スキル

**コマンド総数:** 44

### ワークフロー（`eclusa/workflows/*.md`）

コマンドが参照するオーケストレーションロジックです。以下を含むステップバイステップのプロセスが記述されています：
- `eclusa-tools.cjs init` によるコンテキスト読み込み
- モデル解決を伴うエージェント起動の指示
- ゲート/チェックポイントの定義
- 状態更新パターン
- エラーハンドリングとリカバリー

**ワークフロー総数:** 46

### エージェント（`agents/*.md`）

フロントマターで以下を指定する専門エージェント定義：
- `name` — エージェント識別子
- `description` — 役割と目的
- `tools` — 許可されたツールアクセス（Read、Write、Edit、Bash、Grep、Glob、WebSearchなど）
- `color` — 視覚的な区別のためのターミナル出力色

**エージェント総数:** 16

### リファレンス（`eclusa/references/*.md`）

ワークフローとエージェントが `@-reference` で参照する共有知識ドキュメント：
- `checkpoints.md` — チェックポイントタイプの定義とインタラクションパターン
- `model-profiles.md` — エージェントごとのモデルティア割り当て
- `verification-patterns.md` — 各種アーティファクトの検証方法
- `planning-config.md` — 設定スキーマの全体像と動作
- `git-integration.md` — gitコミット、ブランチ、履歴のパターン
- `questioning.md` — プロジェクト初期化のためのドリーム抽出フィロソフィー
- `tdd.md` — テスト駆動開発の統合パターン
- `ui-brand.md` — 視覚的な出力フォーマットパターン

### テンプレート（`eclusa/templates/`）

すべてのプランニングアーティファクト用のMarkdownテンプレートです。`eclusa-tools.cjs template fill` および `scaffold` コマンドにより、事前構造化されたファイルを作成するために使用されます：
- `project.md`、`requirements.md`、`roadmap.md`、`state.md` — コアプロジェクトファイル
- `phase-prompt.md` — フェーズ実行プロンプトテンプレート
- `summary.md`（+ `summary-minimal.md`、`summary-standard.md`、`summary-complex.md`）— 粒度対応のサマリーテンプレート
- `DEBUG.md` — デバッグセッション追跡テンプレート
- `UI-SPEC.md`、`UAT.md`、`VALIDATION.md` — 専門検証テンプレート
- `discussion-log.md` — ディスカッション監査証跡テンプレート
- `codebase/` — ブラウンフィールドマッピングテンプレート（スタック、アーキテクチャ、規約、懸念事項、構造、テスト、統合）
- `research-project/` — リサーチ出力テンプレート（SUMMARY、STACK、FEATURES、ARCHITECTURE、PITFALLS）

### フック（`hooks/`）

ホストAIエージェントと統合するランタイムフック：

| フック | イベント | 目的 |
|------|-------|---------|
| `eclusa-statusline.js` | `statusLine` | モデル、タスク、ディレクトリ、コンテキスト使用量バーを表示 |
| `eclusa-context-monitor.js` | `PostToolUse` / `AfterTool` | コンテキスト残量35%/25%でエージェント向け警告を注入 |
| `eclusa-check-update.js` | `SessionStart` | Eclusaの新バージョンをバックグラウンドで確認 |
| `eclusa-prompt-guard.js` | `PreToolUse` | `.eclusa/` への書き込みにプロンプトインジェクションパターンがないかスキャン（アドバイザリー） |
| `eclusa-workflow-guard.js` | `PreToolUse` | Eclusaワークフローコンテキスト外でのファイル編集を検出（アドバイザリー、`hooks.workflow_guard` によるオプトイン） |

### CLIツール（`eclusa/bin/`）

17のドメインモジュールを持つNode.js CLIユーティリティ（`eclusa-tools.cjs`）：

| モジュール | 責務 |
|--------|---------------|
| `core.cjs` | エラーハンドリング、出力フォーマット、共有ユーティリティ |
| `state.cjs` | STATE.md の解析、更新、進行、メトリクス |
| `phase.cjs` | フェーズディレクトリ操作、小数番号付け、プランインデックス |
| `roadmap.cjs` | ROADMAP.md の解析、フェーズ抽出、プラン進捗 |
| `config.cjs` | config.json の読み書き、セクション初期化 |
| `verify.cjs` | プラン構造、フェーズ完了度、リファレンス、コミット検証 |
| `template.cjs` | テンプレート選択と変数置換による穴埋め |
| `frontmatter.cjs` | YAMLフロントマターのCRUD操作 |
| `init.cjs` | ワークフロータイプごとの複合コンテキスト読み込み |
| `milestone.cjs` | マイルストーンのアーカイブ、要件マーキング |
| `commands.cjs` | その他コマンド（slug、タイムスタンプ、todos、スキャフォールディング、統計） |
| `model-profiles.cjs` | モデルプロファイル解決テーブル |
| `security.cjs` | パストラバーサル防止、プロンプトインジェクション検出、安全なJSON解析、シェル引数バリデーション |
| `uat.cjs` | UATファイル解析、検証デット追跡、audit-uatサポート |

---

## エージェントモデル

### オーケストレーター → エージェントパターン

```
Orchestrator (workflow .md)
    │
    ├── Load context: eclusa-tools.cjs init <workflow> <phase>
    │   Returns JSON with: project info, config, state, phase details
    │
    ├── Resolve model: eclusa-tools.cjs resolve-model <agent-name>
    │   Returns: opus | sonnet | haiku | inherit
    │
    ├── Spawn Agent (Task/SubAgent call)
    │   ├── Agent prompt (agents/*.md)
    │   ├── Context payload (init JSON)
    │   ├── Model assignment
    │   └── Tool permissions
    │
    ├── Collect result
    │
    └── Update state: eclusa-tools.cjs state update/patch/advance-plan
```

### エージェント起動カテゴリ

| カテゴリ | エージェント | 並列実行 |
|----------|--------|-------------|
| **リサーチャー** | eclusa-project-researcher, eclusa-phase-researcher, eclusa-ui-researcher, eclusa-advisor-researcher | 4並列（stack、features、architecture、pitfalls）; advisorはdiscuss-phase中に起動 |
| **シンセサイザー** | eclusa-research-synthesizer | 逐次（リサーチャー完了後） |
| **プランナー** | eclusa-planner, eclusa-roadmapper | 逐次 |
| **チェッカー** | eclusa-plan-checker, eclusa-integration-checker, eclusa-ui-checker, eclusa-nyquist-auditor | 逐次（検証ループ、最大3回反復） |
| **エグゼキューター** | eclusa-executor | ウェーブ内は並列、ウェーブ間は逐次 |
| **ベリファイアー** | eclusa-verifier | 逐次（全エグゼキューター完了後） |
| **マッパー** | eclusa-codebase-mapper | 4並列（tech、arch、quality、concerns） |
| **デバッガー** | eclusa-debugger | 逐次（インタラクティブ） |
| **オーディター** | eclusa-ui-auditor | 逐次 |

### ウェーブ実行モデル

`execute-phase` では、プランが依存関係に基づいてウェーブにグループ化されます：

```
Wave Analysis:
  Plan 01 (no deps)      ─┐
  Plan 02 (no deps)      ─┤── Wave 1 (parallel)
  Plan 03 (depends: 01)  ─┤── Wave 2 (waits for Wave 1)
  Plan 04 (depends: 02)  ─┘
  Plan 05 (depends: 03,04) ── Wave 3 (waits for Wave 2)
```

各エグゼキューターには以下が与えられます：
- フレッシュな200Kコンテキストウィンドウ
- 実行対象の特定のPLAN.md
- プロジェクトコンテキスト（PROJECT.md、STATE.md）
- フェーズコンテキスト（CONTEXT.md、利用可能な場合はRESEARCH.md）

#### 並列コミットの安全性

同一ウェーブ内で複数のエグゼキューターが実行される場合、2つの仕組みで競合を防止します：

1. **`--no-verify` コミット** — 並列エージェントはpre-commitフックをスキップします（ビルドロックの競合を引き起こす可能性があるため。例：Rustプロジェクトでのcargo lockファイルの競合）。オーケストレーターは各ウェーブ完了後に `git hook run pre-commit` を1回実行します。

2. **STATE.md ファイルロック** — すべての `writeStateMd()` 呼び出しはロックファイルベースの相互排他（`STATE.md.lock`、`O_EXCL` によるアトミック作成）を使用します。これにより、2つのエージェントがSTATE.mdを読み取り、異なるフィールドを変更し、最後の書き込みが他方の変更を上書きする読み取り-変更-書き込みの競合状態を防止します。古いロックの検出（10秒タイムアウト）とジッター付きのスピンウェイトを含みます。

---

## データフロー

### 新規プロジェクトフロー

```
User input (idea description)
    │
    ▼
Questions (questioning.md philosophy)
    │
    ▼
4x Project Researchers (parallel)
    ├── Stack → STACK.md
    ├── Features → FEATURES.md
    ├── Architecture → ARCHITECTURE.md
    └── Pitfalls → PITFALLS.md
    │
    ▼
Research Synthesizer → SUMMARY.md
    │
    ▼
Requirements extraction → REQUIREMENTS.md
    │
    ▼
Roadmapper → ROADMAP.md
    │
    ▼
User approval → STATE.md initialized
```

### フェーズ実行フロー

```
discuss-phase → CONTEXT.md (user preferences)
    │
    ▼
ui-phase → UI-SPEC.md (design contract, optional)
    │
    ▼
plan-phase
    ├── Phase Researcher → RESEARCH.md
    ├── Planner → PLAN.md files
    └── Plan Checker → Verify loop (max 3x)
    │
    ▼
execute-phase
    ├── Wave analysis (dependency grouping)
    ├── Executor per plan → code + atomic commits
    ├── SUMMARY.md per plan
    └── Verifier → VERIFICATION.md
    │
    ▼
verify-work → UAT.md (user acceptance testing)
    │
    ▼
ui-review → UI-REVIEW.md (visual audit, optional)
```

### コンテキスト伝播

各ワークフローステージは後続のステージに供給されるアーティファクトを生成します：

```
PROJECT.md ────────────────────────────────────────────► All agents
REQUIREMENTS.md ───────────────────────────────────────► Planner, Verifier, Auditor
ROADMAP.md ────────────────────────────────────────────► Orchestrators
STATE.md ──────────────────────────────────────────────► All agents (decisions, blockers)
CONTEXT.md (per phase) ────────────────────────────────► Researcher, Planner, Executor
RESEARCH.md (per phase) ───────────────────────────────► Planner, Plan Checker
PLAN.md (per plan) ────────────────────────────────────► Executor, Plan Checker
SUMMARY.md (per plan) ─────────────────────────────────► Verifier, State tracking
UI-SPEC.md (per phase) ────────────────────────────────► Executor, UI Auditor
```

---

## ファイルシステムレイアウト

### インストールファイル

```
~/.claude/                          # Claude Code (global install)
├── commands/eclusa/*.md               # 37 slash commands
├── eclusa/
│   ├── bin/eclusa-tools.cjs           # CLI utility
│   ├── bin/lib/*.cjs               # 15 domain modules
│   ├── workflows/*.md              # 42 workflow definitions
│   ├── references/*.md             # 13 shared reference docs
│   └── templates/                  # Planning artifact templates
├── agents/*.md                     # 15 agent definitions
├── hooks/
│   ├── eclusa-statusline.js           # Statusline hook
│   ├── eclusa-context-monitor.js      # Context warning hook
│   └── eclusa-check-update.js         # Update check hook
├── settings.json                   # Hook registrations
└── VERSION                         # Installed version number
```

他のランタイムでの同等パス：
- **OpenCode:** `~/.config/opencode/` または `~/.opencode/`
- **Gemini CLI:** `~/.gemini/`
- **Codex:** `~/.codex/`（コマンドの代わりにスキルを使用）
- **Copilot:** `~/.github/`
- **Antigravity:** `~/.gemini/antigravity/`（グローバル）または `./.agent/`（ローカル）

### プロジェクトファイル（`.eclusa/`）

```
.eclusa/
├── PROJECT.md              # プロジェクトビジョン、制約、決定事項、発展ルール
├── REQUIREMENTS.md         # スコープ付き要件（v1/v2/スコープ外）
├── ROADMAP.md              # ステータス追跡付きフェーズ分解
├── STATE.md                # 生きたメモリ：位置、決定事項、ブロッカー、メトリクス
├── config.json             # ワークフロー設定
├── MILESTONES.md           # 完了済みマイルストーンのアーカイブ
├── research/               # /eclusa:new-project によるドメインリサーチ
│   ├── SUMMARY.md
│   ├── STACK.md
│   ├── FEATURES.md
│   ├── ARCHITECTURE.md
│   └── PITFALLS.md
├── codebase/               # ブラウンフィールドマッピング（/eclusa:map-codebase から）
│   ├── STACK.md
│   ├── ARCHITECTURE.md
│   ├── CONVENTIONS.md
│   ├── CONCERNS.md
│   ├── STRUCTURE.md
│   ├── TESTING.md
│   └── INTEGRATIONS.md
├── phases/
│   └── XX-phase-name/
│       ├── XX-CONTEXT.md       # ユーザー設定（discuss-phase から）
│       ├── XX-RESEARCH.md      # エコシステムリサーチ（plan-phase から）
│       ├── XX-YY-PLAN.md       # 実行プラン
│       ├── XX-YY-SUMMARY.md    # 実行結果
│       ├── XX-VERIFICATION.md  # 実行後の検証
│       ├── XX-VALIDATION.md    # ナイキストテストカバレッジマッピング
│       ├── XX-UI-SPEC.md       # UIデザインコントラクト（ui-phase から）
│       ├── XX-UI-REVIEW.md     # ビジュアル監査スコア（ui-review から）
│       └── XX-UAT.md           # ユーザー受け入れテスト結果
├── quick/                  # クイックタスク追跡
│   └── YYMMDD-xxx-slug/
│       ├── PLAN.md
│       └── SUMMARY.md
├── todos/
│   ├── pending/            # キャプチャされたアイデア
│   └── done/               # 完了済みtodo
├── threads/               # 永続コンテキストスレッド（/eclusa:thread から）
├── seeds/                 # 将来に向けたアイデア（/eclusa:plant-seed から）
├── debug/                  # アクティブなデバッグセッション
│   ├── *.md                # アクティブセッション
│   ├── resolved/           # アーカイブ済みセッション
│   └── knowledge-base.md   # 永続的なデバッグ知見
├── ui-reviews/             # /eclusa:ui-review からのスクリーンショット（gitignore対象）
└── continue-here.md        # コンテキスト引き継ぎ（pause-work から）
```

---

## インストーラーアーキテクチャ

インストーラー（`bin/install.js`、約3,000行）は以下を処理します：

1. **ランタイム検出** — インタラクティブプロンプトまたはCLIフラグ（`--claude`、`--opencode`、`--gemini`、`--codex`、`--copilot`、`--antigravity`、`--all`）
2. **インストール先の選択** — グローバル（`--global`）またはローカル（`--local`）
3. **ファイルデプロイ** — コマンド、ワークフロー、リファレンス、テンプレート、エージェント、フックをコピー
4. **ランタイム適応** — ランタイムごとにファイル内容を変換：
   - Claude Code: そのまま使用
   - OpenCode: エージェントフロントマターを `name:`、`model: inherit`、`mode: subagent` に変換
   - Codex: コマンドからTOML設定 + スキルを生成
   - Copilot: ツール名をマッピング（Read→read、Bash→executeなど）
   - Gemini: フックイベント名を調整（`PostToolUse` の代わりに `AfterTool`）
   - Antigravity: Googleモデル同等品によるスキルファースト
5. **パス正規化** — `~/.claude/` パスをランタイム固有のパスに置換
6. **設定統合** — ランタイムの `settings.json` にフックを登録
7. **パッチバックアップ** — v1.17以降、ローカルで変更されたファイルを `/eclusa:reapply-patches` 用に `eclusa-local-patches/` へバックアップ
8. **マニフェスト追跡** — クリーンアンインストールのために `eclusa-file-manifest.json` を書き込み
9. **アンインストールモード** — `--uninstall` ですべてのEclusaファイル、フック、設定を削除

### プラットフォーム対応

- **Windows:** 子プロセスでの `windowsHide`、保護ディレクトリへのEPERM/EACCES対策、パスセパレーターの正規化
- **WSL:** WindowsのNode.jsがWSL上で実行されていることを検出し、パスの不一致について警告
- **Docker/CI:** カスタム設定ディレクトリの場所に `CLAUDE_CONFIG_DIR` 環境変数をサポート

---

## フックシステム

### アーキテクチャ

```
Runtime Engine (Claude Code / Gemini CLI)
    │
    ├── statusLine event ──► eclusa-statusline.js
    │   Reads: stdin (session JSON)
    │   Writes: stdout (formatted status), /tmp/claude-ctx-{session}.json (bridge)
    │
    ├── PostToolUse/AfterTool event ──► eclusa-context-monitor.js
    │   Reads: stdin (tool event JSON), /tmp/claude-ctx-{session}.json (bridge)
    │   Writes: stdout (hookSpecificOutput with additionalContext warning)
    │
    └── SessionStart event ──► eclusa-check-update.js
        Reads: VERSION file
        Writes: ~/.claude/cache/eclusa-update-check.json (spawns background process)
```

### コンテキストモニターの閾値

| コンテキスト残量 | レベル | エージェントの動作 |
|-------------------|-------|----------------|
| > 35% | Normal | 警告なし |
| ≤ 35% | WARNING | 「新しい複雑な作業の開始を避けてください」 |
| ≤ 25% | CRITICAL | 「コンテキストがほぼ枯渇、ユーザーに通知してください」 |

デバウンス：繰り返し警告の間隔は5回のツール使用。重大度のエスカレーション（WARNING→CRITICAL）はデバウンスをバイパスします。

### 安全性の特性

- すべてのフックはtry/catchでラップされ、エラー時はサイレントに終了
- stdin タイムアウトガード（3秒）でパイプの問題によるハングを防止
- 古いメトリクス（60秒超）は無視される
- ブリッジファイルの欠落は適切に処理される（サブエージェント、新規セッション）
- コンテキストモニターはアドバイザリーのみ — ユーザーの設定を上書きする命令的なコマンドは発行しない

### セキュリティフック（v1.27）

**Prompt Guard**（`eclusa-prompt-guard.js`）：
- `.eclusa/` ファイルへのWrite/Edit時にトリガー
- プロンプトインジェクションパターン（ロールオーバーライド、指示バイパス、systemタグインジェクション）をスキャン
- アドバイザリーのみ — 検出をログに記録するが、ブロックはしない
- フックの独立性のため、パターンはインライン化（`security.cjs` のサブセット）

**Workflow Guard**（`eclusa-workflow-guard.js`）：
- `.eclusa/` 以外のファイルへのWrite/Edit時にトリガー
- Eclusaワークフローコンテキスト外での編集を検出（アクティブな `/eclusa:` コマンドやTaskサブエージェントがない場合）
- 状態追跡される変更には `/eclusa:quick` や `/eclusa:fast` の使用をアドバイス
- `hooks.workflow_guard: true` によるオプトイン（デフォルト: false）

---

## ランタイム抽象化

Eclusaは統一されたコマンド/ワークフローアーキテクチャを通じて6つのAIコーディングランタイムをサポートしています：

| ランタイム | コマンド形式 | エージェントシステム | 設定場所 |
|---------|---------------|--------------|-----------------|
| Claude Code | `/eclusa:command` | Task起動 | `~/.claude/` |
| OpenCode | `/eclusa-command` | サブエージェントモード | `~/.config/opencode/` |
| Gemini CLI | `/eclusa:command` | Task起動 | `~/.gemini/` |
| Codex | `$eclusa-command` | スキル | `~/.codex/` |
| Copilot | `/eclusa:command` | エージェント委譲 | `~/.github/` |
| Antigravity | スキル | スキル | `~/.gemini/antigravity/` |

### 抽象化ポイント

1. **ツール名マッピング** — 各ランタイムは独自のツール名を持つ（例：ClaudeのBash → Copilotのexecute）
2. **フックイベント名** — Claude Codeは `PostToolUse`、Geminiは `AfterTool` を使用
3. **エージェントフロントマター** — 各ランタイムは独自のエージェント定義形式を持つ
4. **パス規約** — 各ランタイムは異なるディレクトリに設定を保存
5. **モデル参照** — `inherit` プロファイルにより、Eclusaはランタイムのモデル選択に委譲

インストーラーはインストール時にすべての変換を処理します。ワークフローとエージェントはClaude Codeのネイティブ形式で記述され、デプロイ時に変換されます。
