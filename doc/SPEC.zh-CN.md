# Sentinel — SPEC.md（设计文档）

> *Spec-Driven, Subagent-Built, Human-Owned.*
>
> Sentinel 是为 AI4SE 期末项目（项目 A）构建的 Coding Agent Harness。
> 本规约由 `brainstorming` 技能产出，并作为 `writing-plans` 的输入。

---

## 1. 问题陈述

### 1.1 问题

当 LLM 能完成大部分"思考"时，工程师的价值就转移到 **harness** 层——
把一个只会产生"下一步做什么"的模型，封装成一台能稳定可靠工作的系统
的工程。核心等式是：

```
Agent = LLM + Harness
```

LLM 相当于 CPU；harness 是其余一切：决策封装、工具、上下文/记忆、治理
护栏、反馈闭环与配置。今天大多数用户从闭源产品（Claude Code、Cursor
等）免费获得 harness，从不触碰这一层。Sentinel 把这一层显式化、并自行
实现。

### 1.2 目标用户

- **开发者**：希望在浏览器中观看 agent 完成一个编码任务，并对危险动作
  通过人工审批（HITL）进行门控。
- **学生/研究者**：希望得到一个小巧、可读、**可用 mock-LLM 测试**的
  harness 内核，以研究治理、反馈与工具分发在代码层面究竟如何工作——
  而不是停留在提示词层面。

### 1.3 为何值得构建

Sentinel 回答课程的核心命题——*当 LLM 能完成大部分编码时，工程师的
价值在哪里？*——其方式是把这个价值本身作为交付物：治理、反馈、上下文、
安全与分发。它是"用一个 harness（Superpowers）去造另一个 harness"，
从而对 agentic-SE 方法论形成第一手的批判性理解。深度维度是**治理**，
因为它是最代码密集、最确定性、最可单测的机制——最能证明 harness 是
真正的工程，而非一句提示词。

---

## 2. 用户故事

所有故事遵循 INVEST 原则（独立、可协商、有价值、可估算、小、可测试）。

- **US1 — 运行编码任务。** 作为开发者，我希望通过 WebUI 发送一个编码
  任务（如"修复 `tests/test_foo.py` 中失败的测试"），并观看 agent 读
  文件、改代码、跑测试、汇报结果，从而把一个边界清晰的编码杂事委派出去。
- **US2 — 对危险动作门控（HITL）。** 作为开发者，当 agent 提出危险动作
  （`rm -rf`、`git push --force`、删除数据库）时，我希望看到一张内联的
  批准/拒绝卡片，含动作、风险等级与原因，从而任何破坏性操作都不得未经
  我明确同意而执行。
- **US3 — 无响应即失败关闭。** 作为开发者，若我在超时内未响应审批请求，
  我希望该动作被**拒绝**（不执行），从而疏忽永远不会造成损害。
- **US4 — 从测试反馈自我修正。** 作为开发者，当 agent 跑测试失败时，
  我希望 agent 收到结构化的失败反馈并据此改变下一步动作以修复失败，
  从而无需我推动即可闭环。
- **US5 — 声明式配置行为。** 作为开发者，我希望用一份 YAML 配置来设定
  供应商/模型、允许的工具、风险阈值、沙箱设置与护栏规则，从而不改代码
  即可约束 agent。
- **US6 — 安全录入密钥。** 作为开发者在全新机器上，我希望有一条引导式、
  隐藏输入的命令，把 OpenAI/Anthropic 密钥存入操作系统钥匙串，并有一条
  永不回显明文的状态命令，从而密钥永不落入代码、git 或日志。
- **US7 — 审计一次运行。** 作为开发者，在一次会话之后，我希望查看审计
  轨迹（每个动作、其护栏决策、风险等级与结果），从而回顾 agent 做了
  什么、每个动作为何被允许或拦截。
- **US8 — 离线运行测试。** 作为维护者，我希望有一键测试套件，用 mock
  LLM、无网络地覆盖每个核心机制，从而在 CI 中确定性验证 harness 逻辑。

---

## 3. 功能规约（按模块）

每个模块列出 **输入 / 行为 / 输出 / 边界 / 错误处理**。模块映射到
harness 的六个维度（§A.3）外加 WebUI 与支撑基础设施。

### 3.1 决策 / 主循环（`agent_loop`）

- **输入：** `RunContext`（任务、配置快照、记忆片段、近期轮次、工具
  结果），一个 `LLMProvider`、一个 `ToolRegistry`、一个
  `GuardrailPipeline`、一个 `ApprovalPolicy`、`max_turns`。
- **行为：** `async def agent_loop(...) -> AsyncIterator[Event]`。每轮：
  组织上下文 → 调用 `llm.complete(messages, tools)` → 把响应解析为一个
  或多个 `Action` → 逐个送入护栏管线 → 若 `RequiresApproval`，产出
  `ApprovalNeeded` 并等待策略 → 若允许，在沙箱中执行工具 → 捕获结果 →
  运行反馈校验器 → 把反馈回灌上下文 → 重复。停止条件：LLM "完成"
  信号、`max_turns`、或不可恢复错误。
- **输出：** 事件流：`TurnStarted`、`LLMResponse`、`ActionRequested`、
  `ApprovalNeeded`、`ActionExecuted`、`FeedbackReceived`、`TurnComplete`、
  `Stopped`。
- **边界：** 循环在测试（`MockLLM` + `AutoApprove`）与生产（真实 LLM +
  `HumanApprove`）中是**同一份代码**；只有被注入的协作者变化。循环内除
  注入接口外无任何 I/O。
- **错误：** LLM 调用失败 → 有限退避重试，然后产出
  `Stopped(reason=llm_error)`。LLM 响应不可解析 → 产出 `ParseError` 事件
  并继续（把解析失败回灌给 LLM 重新提示）。工具执行失败 → 作为
  `ActionExecuted(success=False)` 捕获并作为反馈回灌。

### 3.2 工具（`Tool` 层）

- **输入：** `Action(tool, args, ...)`。
- **行为：** `Tool` 协议，`execute(args, sandbox) -> ToolResult`。注册表
  把工具名映射到 `Tool` 实例。MVP 集合：`read_file`、`write_file`、
  `list_dir`、`run_shell`、`run_tests`、`search`。每个工具声明默认
  `risk_level`。执行通过可插拔的 `SandboxBackend`：
  `DockerSandbox`（主，生产）或 `InProcessSandbox`（受限工作目录，用于
  无 Docker 环境与 mock-LLM 测试）。结果截断以适配上下文。
- **输出：** `ToolResult(success, stdout, stderr, truncated, artifacts)`。
- **边界：** 工具绝不在*某个*沙箱后端之外运行；路径被限制在沙箱工作区。
  `InProcessSandbox` 强制与 `DockerSandbox` 相同的路径边界（纵深防御：
  无论后端如何，`ScopeFenceGuardrail` 都在执行*之前*检查路径）。新增
  工具 = 注册一个类 + 声明其风险。
- **错误：** 沙箱不可用 → `ToolResult(success=False, error)`。命令未找到
  / 非零退出 → 作为正常结果捕获（非零是*信息*，不是 harness 错误）。
  输出超限 → 带标记截断。

### 3.3 治理（`Guardrail` 管线 + HITL + 审计）— **深度维度**

详见 §9。此处为摘要：

- **输入：** `Action` + `RunContext`。
- **行为：** 一条可组合的 `Guardrail` 管线，每个返回
  `GuardrailResult(decision, reason, risk_level)`。聚合规则：任一 `Deny`
  → `Deny`（短路）；否则任一 `RequiresApproval` → `RequiresApproval`
  （最高风险胜出）；否则 `Allow`。`RequiresApproval` 动作进入 HITL 状态
  机；由 `ApprovalPolicy` 解析。每个决策追加到审计日志。
- **输出：** `GuardrailResult`；下游 `ApprovalNeeded` / `ActionExecuted` /
  `Skipped` 事件；`AuditEntry` 行。
- **边界：** 护栏是 `(action, ctx)` 的纯函数——无 LLM、无网络、无时间
  效应。失败关闭：超时或策略错误 → `Denied`。
- **错误：** 护栏抛异常 → 视为 `Deny(reason=guardrail_error)`（失败关闭）。
  非法 HITL 转换 → 抛异常（编程错误，在测试中捕获）。

### 3.4 反馈（`Validator` 层）

- **输入：** 来自 `run_tests` / `run_shell` 动作的 `ToolResult`。
- **行为：** 循环通过检查动作的 tool/args 选择 `Validator`（如
  `run_tests` → `pytest` 校验器；`run_shell` 含 `ruff …` → `ruff`
  校验器；`run_shell` 含 `mypy …` → `mypy` 校验器）。校验器把输出解析
  为结构化 `Feedback(pass, failures)`，每个失败被分类
  （`syntax_error`、`assertion_failure`、`import_error`、`type_error`、
  `unknown`）。反馈回灌到下一轮上下文。
- **输出：** `Feedback` 对象 + `FeedbackReceived` 事件。
- **边界：** 校验器是确定性解析器；绝不调用 LLM。未知输出 → `unknown`
  分类（仍有用：通过/失败已知）。
- **错误：** 不可解析输出 → `Feedback(pass=unknown, failures=[])`；原始
  输出仍附给 agent。

### 3.5 记忆（MVP，自行实现）

- **输入：** 一个查询（任务 + 近期上下文）。
- **行为：** 按关键词 + 简单 TF-IDF 检索相关 `Memory` 行（项目约定、
  历史决策、代码库笔记）。每轮作为上下文片段载入，而非全量载入。当
  agent（或用户）记录决策/约定时写入。
- **输出：** 排序后的记忆片段列表。
- **边界：** 存储与检索由 Sentinel 自身代码实现（不使用框架自带 memory）。
  MVP 不强制向量嵌入；文本上的 TF-IDF 已足够且自包含。
- **错误：** 存储失败 → 记日志并继续（记忆是尽力而为，不在关键路径）。

### 3.6 配置

- **输入：** 一份 YAML 文件（`sentinel.yaml`）。
- **行为：** 载入供应商+模型、允许的工具、风险阈值、沙箱设置（镜像、
  挂载、默认关闭网络）、护栏规则、`max_turns`、审批超时。每会话存一份
  快照，使运行可由配置复现。
- **输出：** `Config` 对象 + `ConfigSnapshot` 行。
- **边界：** 未知键 → 警告（忽略）；缺失必需键 → 启动错误。配置绝不
  含密钥（密钥在钥匙串）。
- **错误：** 非法 YAML / schema → 启动时快速失败并给出清晰信息。

### 3.7 WebUI（FastAPI + Open Design 前端）

- **输入：** 每会话一条 WebSocket 连接；REST 用于会话列表 / 审计轨迹 /
  配置。
- **行为：** 消费 `agent_loop` 异步生成器；把 `Event` 流推送到浏览器；
  把 `ApprovalNeeded` 渲染为内联批准/拒绝卡片；把审批结果回灌到
  `HumanApprove` 策略。前端用 **Open Design** 构建（`linear-app` 设计
  系统、`dashboard` skill）。
- **输出：** 一个实时流式聊天 + 事件日志 + HITL 面 + 审计轨迹视图。
- **边界：** WebUI 是可测试核心之上的传输/展示层；不含任何 harness 逻辑。
  审批中途 WebSocket 断开 → 待审动作超时（失败关闭）。
- **错误：** WebSocket 错误 → 会话标记 `interrupted`；用户可从最近
  checkpoint 轮次恢复。

### 3.8 凭据管理（`config` CLI）

- **输入：** `sentinel config set-key --provider <p>`（隐藏输入）、
  `sentinel config status`、`sentinel config clear-key --provider <p>`。
- **行为：** 通过 Python `keyring` 在 OS 钥匙串中存取/清除密钥。
  `status` 打印 `openai: set / anthropic: not set`——永不回显明文。
  支持 `.env` 加载作为文档化的回退。
- **输出：** 退出码 + 状态行。
- **边界：** 密钥绝不入日志、绝不写入配置文件、绝不回显。`.env` 为明文
  （文档化风险）。
- **错误：** 钥匙串后端缺失 → 回退到带主密码的加密文件存储（并告警）。
  密钥错误 → 首次调用时作为 LLM 鉴权错误暴露。

---

## 4. 非功能性需求

### 4.1 性能

- 单个 agent 轮次（不计 LLM 调用，因其占大头）的 harness 侧工作
  （解析 + 护栏 + 审批 + 执行 + 反馈）须在笔记本上 **< 200 ms** 完成。
- WebSocket 事件延迟（harness → 浏览器）本地部署 **< 100 ms**。
- 沙箱容器启动 **< 5 s**（热镜像）；冷启动首次可能更久，并在 UI 中报告。

### 4.2 安全（含凭据威胁模型）

**凭据威胁模型：**

| 威胁 | 对策 |
|---|---|
| 密钥在源码中 | 绝不硬编码；pre-commit 钩子扫描密钥模式（`sk-...`、`sk-ant-...`）。 |
| 密钥在 git 历史 | `.env` 被 `.gitignore`；pre-commit 守卫拦截含密钥模式的提交；若泄露则轮换。 |
| 密钥在日志 | 日志脱敏：`Authorization` 头与密钥材料绝不入日志；强制使用脱敏格式器。 |
| 密钥在进程环境（对其他进程可见） | 优先用钥匙串（运行时取用，不持久化于环境）；`.env` 文档化为明文且进程环境可见。 |
| 密钥在目标/分发机器 | README 说明目标机上的钥匙串配置；Docker 镜像从钥匙串或 `docker run` 时提供的环境变量读取密钥。 |

**沙箱安全：** 沙箱容器以非 root 运行、默认无网络、资源受限
（CPU/内存）、系统路径只读、工作区挂载受限。网络启用按动作粒度且需审批。

**失败关闭默认：** 任何歧义（护栏错误、审批超时、策略失败）一律拒绝，
绝不执行。

### 4.3 可用性

- 一键本地运行（`sentinel serve` 或 `docker run`）。
- 引导式首次密钥录入，隐藏输入。
- WebUI 在单一流式视图中展示 agent 的推理、动作、审批与结果；无需读
  日志即可跟随一次运行。

### 4.4 可观测性

- 每个动作产出一条 `AuditEntry`（护栏、决策、风险、结果、时间戳）。
- 审计轨迹可查询（按工具 / 风险 / 决策 / 时间）并在 WebUI 渲染。
- 结构化日志（JSON），密钥脱敏；日志级别可配置。

### 4.5 可移植性

- Python 3.11+。运行于 macOS / Windows / Linux。
- 沙箱后端需要 Docker；harness 本身在 mock-LLM 测试中无需 Docker。

---

## 5. 系统架构

### 5.1 组件图

```
┌──────────────────────── 浏览器（Open Design 前端）─────────────────────────┐
│  聊天输入 · 流式事件日志 · 内联 HITL 批准/拒绝 · 审计视图                  │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ WebSocket（事件）+ REST（列表/审计）
┌──────────────────────────────────▼────────────────────────────────────────┐
│  WebUI 层（FastAPI）                                                        │
│  - 消费异步生成器，流式推送事件，解析 HumanApprove                          │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ 驱动
┌──────────────────────────────────▼────────────────────────────────────────┐
│  Harness 核心（可用 MockLLM + AutoApprove 测试，无网络/Docker）            │
│                                                                            │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────────────┐  │
│  │ agent_loop   │──▶│ LLMProvider  │   │ GuardrailPipeline（深度）      │  │
│  │ (异步生成器) │   │ (OpenAI/     │   │  Pattern/ScopeFence/           │  │
│  │              │   │  Anthropic/  │   │  SandboxBoundary/RiskClassify  │  │
│  │              │   │  Mock)       │   │  + ApprovalPolicy + HITL FSM  │  │
│  │              │   └──────────────┘   │  + AuditLog                     │  │
│  │              │──▶┌──────────────┐   └───────────────────────────────┘  │
│  │              │   │ ToolRegistry │                                      │
│  │              │   │ (read/write/ │                                      │
│  │              │   │  shell/test) │                                      │
│  │              │   └──────┬───────┘                                      │
│  │              │──▶┌──────▼───────┐   ┌───────────────────────────────┐  │
│  │              │   │ Validators   │   │ Memory（SQLite + TF-IDF）        │  │
│  │              │   │ (pytest/ruff/│   │ Config（YAML + 快照）            │  │
│  │              │   │  mypy)       │   │                                 │  │
│  └──────────────┘   └──────────────┘   └───────────────────────────────┘  │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ 工具执行
┌──────────────────────────────────▼────────────────────────────────────────┐
│  Docker 沙箱容器（每会话）                                                  │
│  受限工作区挂载 · 默认无网络 · 非 root · 资源受限                          │
└────────────────────────────────────────────────────────────────────────────┘
                                   │
                          外部 LLM 供应商（OpenAI / Anthropic）
```

### 5.2 数据流（一轮）

1. 用户经浏览器发送任务 → WebSocket → `agent_loop` 启动。
2. 循环调用 `llm.complete(...)` → LLM 返回一个动作（如
   `run_shell: pytest`）。
3. 动作进入 `GuardrailPipeline` → `Allow` / `Deny` /
   `RequiresApproval`。
4. 若 `RequiresApproval` → 循环产出 `ApprovalNeeded` → 浏览器渲染
   批准/拒绝卡片 → `HumanApprove` 等待回复（超时 → 失败关闭拒绝）。
5. 若允许 → 工具在 Docker 沙箱中执行 → `ToolResult`。
6. `Validator` 解析结果 → `Feedback` → 回灌上下文。
7. 循环继续直到 `Stopped`（完成 / `max_turns` / 错误）。

### 5.3 外部依赖

- **LLM 供应商：** OpenAI（chat completions API）、Anthropic（messages
  API）——位于 `LLMProvider` 抽象之后。
- **沙箱：** Docker 守护进程（经 socket 挂载）用于沙箱容器。
- **库：** `fastapi`、`uvicorn`、`websockets`、`keyring`、`pytest`、
  `pytest-asyncio`、`docker`（Python SDK）、`pyyaml`、`sqlite3`（标准库）。
  Open Design 用于前端构建。

---

## 6. 数据模型

存储：SQLite（基于文件，无服务器）。所有 schema 为示意；最终 DDL 在
实现中。

- **Session** — `id`（主键）、`created_at`、`task`（文本）、`status`
  （`running|completed|interrupted|error`）、`config_snapshot_id`（外键）。
- **Turn** — `id`（主键）、`session_id`（外键）、`index`（整数）、
  `llm_response`（文本）、`status`。
- **Action** — `id`（主键）、`turn_id`（外键）、`tool`、`args`（json）、
  `risk_level`（`low|medium|high|critical`）、`governance_decision`
  （`allow|deny|require_approval`）、`status`
  （`proposed|executing|executed|failed|skipped`）、`result`（json）。
- **Approval** — `id`（主键）、`action_id`（外键，唯一）、`decision`
  （`approved|denied|timeout`）、`decided_by`（文本）、`decided_at`、
  `reason`。
- **Feedback** — `id`（主键）、`action_id`（外键）、`kind`
  （`pytest|ruff|mypy`）、`pass`（布尔）、`failures`（json 数组）。
- **AuditEntry** — `id`（主键）、`action_id`（外键）、`guardrail`（文本）、
  `decision`、`risk_level`、`timestamp`、`outcome`。
- **Memory** — `id`（主键）、`kind`（`convention|decision|note`）、`key`、
  `content`（文本）、`created_at`。
- **ConfigSnapshot** — `id`（主键）、`session_id`（外键）、`config_yaml`
  （文本）。

**约束：** 每个 `Action` 一条 `Approval`（1:1）；一个 `Action` 可有多条
`AuditEntry`（每次护栏运行一条）；`Action.status` 的转换由 HITL 状态机
治理（§9.4）。

---

## 7. 凭据与分发设计

### 7.1 凭据存储、录入、更新、清除

- **存储：** 经 Python `keyring` 使用 OS 钥匙串（macOS Keychain /
  Windows Credential Manager / Linux Secret Service）。回退：带主密码的
  加密文件（当无钥匙串后端可用时）。
- **录入（首次运行）：** `sentinel config set-key --provider openai` 以
  隐藏输入（`getpass`）提示；密钥写入钥匙串，绝不写入磁盘配置。
- **查看状态：** `sentinel config status` 打印 `openai: set /
  anthropic: not set`——永不回显明文。
- **更新 / 清除：** `sentinel config set-key --provider openai`（覆盖）；
  `sentinel config clear-key --provider anthropic`（从钥匙串删除）。
- **`.env` 回退：** 经 `python-dotenv` 支持，文档化为明文 + 进程环境
  可见；仅推荐用于本地开发。

### 7.2 分发

- **主：Docker 镜像。** 单条 `docker build` + 单条 `docker run`。镜像含
  FastAPI 后端 + 构建好的 Open-Design 前端。挂载 Docker socket
  （`/var/run/docker.sock`）以按会话生成沙箱容器。推送到公开 registry
  （GitHub Container Registry）。
- **次：PyPI 包。** `pip install sentinel-harness` 用于无 Docker 的本地
  使用；回退到 `InProcessSandbox` 后端（相同路径边界，无容器隔离）——
  适合演示与本地单用户使用。
- **README** 说明：获取 + 运行命令、**目标机上的密钥配置**（钥匙串配置，
  或 `docker run -e OPENAI_API_KEY=...`）、已知限制（沙箱需 Docker；
  钥匙串平台支持矩阵）。

### 7.3 部署

- 容器化部署到免费层主机（Render / Fly.io / Railway）以满足"可访问
  WebUI URL"要求。README 说明部署架构与 CI/CD。

---

## 8. 技术选型与理由

| 选择 | 理由 |
|---|---|
| **Python 3.11+** | LLM/AI 生态最丰富；用 `pytest`/`pytest-asyncio` 易做 mock-LLM 测试；迭代快；agent harness 的天然之选。 |
| **异步生成器事件循环** | 实时流式 UX + 干净的 HITL（审批是可注入策略）；同一循环在测试（`MockLLM` + `AutoApprove`）与生产中运行。 |
| **供应商无关的 LLM 层** | 在一个 `LLMProvider` 协议后支持 OpenAI + Anthropic；mock 位于同一接口之后，故所有核心测试与供应商无关。 |
| **FastAPI + WebSocket** | 原生异步、一等公民 WebSocket、审计/配置的简单 REST；与异步生成器干净配合。 |
| **Open Design（`linear-app`、`dashboard` skill）** | 课程推荐的设计工具；`linear-app` 给出契合编码 harness 的干净开发者工具美学；`dashboard` skill 契合聊天 + 审计布局。 |
| **Docker 沙箱** | 强隔离；沙箱本身即一层护栏（无网络、非 root、资源受限）；治理叙事强。 |
| **SQLite** | 基于文件、无服务器、对单用户会话/审计数据足够；CI 中可平凡测试。 |
| **OS 钥匙串（`keyring`）** | 跨平台安全存储；无需自造加密即可满足凭据安全要求。 |
| **GitHub 为主 + `.gitlab-ci.yml` 用于 NJU** | GitHub 用于公开仓库 + PR 工作流；`.gitlab-ci.yml` 含 `unit-test` job 以满足 NJU GitLab 提交要求。 |

---

## 9. 领域与机制设计 [A.5]

本节回答 **coding** 领域的四个机制问题，并说明每个机制如何被**编码**
（而非提示），满足 §A.4-B/C。

### 9.1 四个机制问题（coding 领域）

- **动作 / 工具：** 读写文件、执行 shell、跑测试、搜索。每个工具是一个
  `Tool` 类，声明风险等级；执行被限制在 Docker 沙箱内。
- **客观反馈信号：** 运行 `pytest` / `ruff` / `mypy` 产生确定性、可解析
  的输出。`Validator` 把它解析为结构化 `Feedback`（通过/失败 + 分类失败）
  并回灌上下文。这是*代码*，不是"请自行检查你的工作"。
- **危险动作：** `rm -rf`、`DROP TABLE`、`git push --force`、
  `curl … | sh`、工作区外写入、读取 `~/.ssh` / `.env` / `**/*.key`、
  无网络沙箱中的网络访问。这些由护栏（§9.2）拦截并由 HITL（§9.4）门控。
- **记忆：** 项目约定、历史决策、代码库笔记——存于 SQLite，按关键词 +
  TF-IDF 检索，每轮作为片段载入。

### 9.2 深度维度：为何治理，以及如何编码

**为何治理。** 治理是最代码密集、最确定性、最可单测的维度。它有最清晰
的"机制 = 代码"形态：一个 `guardrail(action)` 函数对 `rm -rf /` 每次都
返回 `Deny`，全程无 LLM 参与。它还承载最强的安全叙事（失败关闭、HITL、
审计），这正是"当 LLM 做编码时工程师拥有什么"的核心。

**如何编码。** 四个可组合的纯函数护栏 + 一个可注入的审批策略 + 一个
HITL 状态机 + 一个审计日志。

```python
# Action 模型——治理检查结构化动作，绝不检查模型的原始文本。
@dataclass
class Action:
    tool: str
    args: dict
    raw_source: str
    turn_id: str

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"

@dataclass
class GuardrailResult:
    decision: Decision
    reason: str
    risk_level: RiskLevel   # low|medium|high|critical
    guardrail_name: str

class Guardrail(Protocol):
    name: str
    def check(self, action: Action, ctx: RunContext) -> GuardrailResult: ...
```

具体护栏（每个可独立单测，无 LLM）：

- **`PatternGuardrail`** — 对 shell 命令与参数做正则/关键词匹配。捕获
  `rm -rf`、`DROP TABLE`、`git push --force`、`curl … | sh`、`chmod 777`、
  fork bomb。规则集可经 YAML 配置。
- **`ScopeFenceGuardrail`** — 路径边界强制。写入限制在工作目录；读取
  敏感路径（`~/.ssh`、`~/.aws`、`.env`、`**/credentials*`、`**/*.key`）
  被拦截。可配置允许/拒绝路径 glob。与物理沙箱挂载纵深防御。
- **`SandboxBoundaryGuardrail`** — 标记需要网络的动作（`pip install`、
  `curl`、`git clone`，因沙箱默认无网络）；标记资源密集动作。返回
  `RequiresApproval` 在此也可触发沙箱重配（如为本动作启用网络）。
- **`RiskClassifierGuardrail`** — 由工具 + 参数 + 模式匹配给出
  `low/medium/high/critical`。驱动审批阈值。

**管线聚合：** 任一 `Deny` → 最终 `Deny`（短路，失败关闭）；否则任一
`RequiresApproval` → 最终 `RequiresApproval`（最高风险胜出）；否则
`Allow`。

### 9.3 可注入的审批策略（可测性的枢纽）

```python
class ApprovalPolicy(Protocol):
    async def approve(self, action: Action, r: GuardrailResult) -> Approval: ...
```

实现：`AutoApprove` / `AutoDeny`（测试，确定性，无 I/O）；
`ThresholdApprove`（自动批准 low/medium，high/critical 升级）；
`HumanApprove`（生产；产出 `ApprovalNeeded`，等待 WebSocket 回复，
**超时 → 失败关闭拒绝**）。因策略被注入，*同一份* `agent_loop` 在测试
与生产中运行。

### 9.4 HITL 状态机

每个 `RequiresApproval` 动作走一个状态机；转换是代码，每次产出一条
`AuditEntry`：

```
Proposed → Evaluating → PendingApproval → {Approved | Denied | Timeout}
                                              ↓ Approved            ↓ Denied/Timeout
                                           Executing              Skipped
                                              ↓
                                        Executed | Failed
```

- **超时 → `Denied`（失败关闭）：** 任何动作未经明确审批绝不执行。
- 非法转换抛异常（如 `PendingApproval → Executing` 被禁止）。
- 可直接测试：构造 `PendingApproval`，注入 `Approved` → 断言
  `Executing`；注入超时 → 断言 `Skipped`。

### 9.5 审计日志

只追加的 SQLite 记录，含每个动作 + 护栏决策 + 风险等级 + 原因 + 结果。
可按工具 / 风险 / 决策 / 时间查询。在 WebUI 中作为运行的审计轨迹渲染。

### 9.6 确定性可测性（满足 §A.4-C）

下列每行都在**无 LLM、无网络、无 Docker** 下运行：

```python
assert guardrail(Action("run_shell", {"cmd": "rm -rf /"})).decision == DENY
assert guardrail(Action("write_file", {"path": "../../etc/passwd"})).decision == DENY
assert guardrail(Action("run_shell", {"cmd": "pytest"})).decision == ALLOW
# HITL：注入 Approved → Executing；注入 Timeout → Skipped
# 审计：跑一段脚本化序列，断言精确的条目列表
```

### 9.7 机制演示（满足 §A.6）

一段在 `MockLLM` 下可复现的脚本/测试：

1. **① 治理拦截：** `MockLLM` 脚本化 `rm -rf /`；护栏拒绝；断言事件
   序列显示 `Deny` 且无执行。
2. **② 反馈自我修正：** 注入一次失败的 `pytest` 运行；`Validator` 产出
   `Feedback(pass=False, failures=[assertion_failure])`；断言 agent 的下一
   动作改变（如它读取失败测试并编辑源码）。
3. **③ HITL 深度：** `MockLLM` 脚本化一个高风险动作；产出
   `ApprovalNeeded`；注入 `Approved` → 动作执行；注入 `Denied` → 跳过；
   注入 `Timeout` → 失败关闭跳过。断言状态 + 审计条目。

---

## 10. 验收标准

每项功能的"完成"均可客观核验。

- **AC1（端到端运行）：** 用真实 LLM 密钥，agent 完成一个简单编码任务：
  读文件 → 编辑 → 跑 `pytest` → 修复失败 → 汇报完成。在 WebUI 中作为
  完整事件流可见。
- **AC2（六维度可运行）：** 决策/工具/记忆/治理/反馈/配置均有可运行的
  最小实现；闭环（动作 → 反馈 → 修正动作）无需人工推动。
- **AC3（治理拦截）：** `rm -rf /`、越界写入、敏感路径读取被护栏拒绝；
  高风险动作产出 `ApprovalNeeded` 并由 WebUI 批准/拒绝卡片门控。
- **AC4（失败关闭）：** 超时的审批被拒绝（不执行）。
- **AC5（mock-LLM 测试）：** 完整 mock-LLM 测试套件离线确定性通过
  （`make test`，无网络、无 Docker、无真实 LLM）。
- **AC6（机制演示）：** §9.7 的演示（①②③）在 `MockLLM` 下复现。
- **AC7（凭据）：** 经 `sentinel config set-key` 设置的密钥存于钥匙串；
  `git log` / 源码 / 日志不含密钥材料（由 pre-commit 扫描验证）。
- **AC8（分发）：** `docker build && docker run` 在全新机器上启动
  WebUI；部署 URL 公网可访问。
- **AC9（审计）：** 一次会话中的每个动作都有 `AuditEntry` 行，可经
  WebUI 审计视图查询。

---

## 11. 风险与未决问题

- **R1 — Docker socket 挂载。** 经挂载的 Docker socket 生成沙箱容器是
  一个安全面并增加复杂度。*对策：* 沙箱镜像被加固（非 root、无网络、
  资源受限）；socket 绝不暴露给 agent 自身（仅 harness 使用）。
- **R2 — LLM 输出解析脆弱性。** 动作解析器须对畸形模型输出健壮。
  *对策：* schema 校验的工具调用（供应商支持时用 function-calling）；
  不可解析输出走 `ParseError` 事件 + 重新提示路径。
- **R3 — 异步测试复杂度。** 异步生成器比同步代码略难测试。*对策：*
  `pytest-asyncio` + 可注入策略使 mock-LLM 测试简单且确定性。
- **R4 — Open Design 集成曲线。** 把 Open Design 生成的前端接到
  FastAPI WebSocket 后端是一个学习步骤。*对策：* 前端面保持最小
  （聊天 + 事件日志 + HITL 卡片 + 审计视图）。
- **R5 — 开发期真实 LLM 成本。** *对策：* mock-LLM 优先测试；真实 LLM
  仅用于端到端冒烟检查。
- **R6 — 范围蔓延。** 六个维度诱使铺开。*对策：* MVP 切分（§3）使五个
  维度保持最小；仅治理深入。
- **OQ1 — 仓库托管。** 已确认：GitHub 为主（公开仓库 + PR 工作流）+
  一份含 `unit-test` job 的 `.gitlab-ci.yml` 用于 NJU GitLab 提交镜像。
  CI 在 GitHub Actions 上运行；`.gitlab-ci.yml` 保持同步，且提交前必须
  在 NJU GitLab 上通过。
- **OQ2 — 沙箱网络。** 默认无网络；按动作启用网络需审批。是否允许
  `pip install`（编码任务中常见）默认带审批还是默认拒绝，是一个配置
  决策，默认为*需审批*。

---

*SPEC.md 结束。下一步：`writing-plans` 技能基于本规约产出 `PLAN.md`，
此前需用户审阅本文档。*
