# Sentinel — AGENT_LOG.md（过程日志）

> 按时间顺序记录关键节点。每条包含：时间戳与 task 编号、触发的 Superpowers
> 技能、关键 prompt / context 配置、subagent 输出关键片段或 commit hash、
> 人工干预（修改了什么、为什么）、学到的教训。
>
> 这是实现工作中最重要的"过程证据"（通用要求 §4.9）。

---

## Phase 0 · Brainstorming & Planning（2026-07-12）

### L-0.1 · brainstorming：从"AI 编程助手"到"harness 内核"
- **技能**：`superpowers:brainstorming`
- **时间**：2026-07-12 全天
- **关键过程**：智能体追问"交付的是再造的 harness 还是现成框架上的配置"，
  使项目转向自研 harness 内核；随后收敛 8 条用户故事（US1–US8）、10 节
  SPEC，并把**治理（governance）**定为 deep dimension。详见
  `docs/SPEC_PROCESS.md` §2–§3。
- **产出**：`docs/SPEC.md`（初稿）
- **人工干预**：否决"向量库记忆"建议，改为 SQLite + TF-IDF；把 WebUI 降级
  为无 harness 逻辑的 transport 层。

### L-0.2 · writing-plans：产出两阶段 PLAN
- **技能**：`superpowers:writing-plans`
- **时间**：2026-07-12 晚
- **关键决策**：为满足"mock-LLM 可单测、无网络"的硬标准，拆为
  - `docs/PLAN.md`（Phase 1，16 个 task：内核 + 治理 + 机制演示）
  - `docs/PLAN-PHASE-2.md`（Phase 2，11 个 task：真实 LLM + WebUI +
    凭据 + 分发）
- **每 task 含**：目标 / 文件 / 实现要点 / 验证步骤（含失败测试）。
- **教训**：plan 里的代码块必须与 SPEC 类型签名逐字一致；后续冷启动验证
  证明，任何"留给实现者发挥"的表述都会让 subagent 卡住。

---

## Phase 1 · 内核实现（2026-07-12，inline 会话，主开发 agent = 人类 + OpenCode）

> 采用 executing-plans 风格逐 task 内联推进（Phase 1 用 `feat(core)`/
> `feat(governance)` 等 Conventional Commits 直接在 main 上提交，每步
> TDD：先红后绿）。

| Task | Commit | 说明 |
|---|---|---|
| T1 脚手架 | `7b78d39` → `916cbb0` | 初始仓库 + pytest 配置 |
| T2 核心类型 | `f802bae`，修复 `ec0f0cd` | Action/Decision/Feedback/Event |
| T3 LLM 抽象 | `58aa1c4` | LLMProvider 协议 + MockLLM |
| T4 工具层 | `de6777f` | Tool 协议 + ToolRegistry |
| T5 沙箱 | `91ee50c` | InProcessSandbox（路径边界） |
| T6 模式护栏 | `14997c0`，加固 `2c93ddd` | PatternGuardrail（含绕过加固） |
| T7 三类护栏 | `3b2311a` | ScopeFence/SandboxBoundary/RiskClassifier |
| T8 流水线 | `bfab311` + `c2756a5` | GuardrailPipeline 聚合 |
| T9 审批策略 | `e8f85cd` + `e20bdb5` | AutoApprove/AutoDeny/ThresholdApprove |
| T10 HITL | `f049803` | HITL 状态机（fail-closed） |
| T11 审计 | `e67cfb9` | append-only AuditLog |
| T12 反馈 | `0becacd` | pytest/ruff/mypy 校验器 |
| T13 主循环 | `9807435`，修复 `8b4643c` | agent_loop 事件流 |
| T14 记忆 | `add49ba` | SQLite + TF-IDF（自研） |
| T15 配置 | `a4e0d9e` | YAML 配置加载 |
| T16 机制演示 | `0eb386a` | §A.6 演示（拦截/自修正/HITL） |
| 最终评审修复 | `255b8d0` | 关闭评审发现的缺口 |

- **技能**：`executing-plans` + `test-driven-development`（每 task 红→绿→
  重构，先失败测试后实现）。
- **人工干预的关键节点**：
  1. `ec0f0cd`：评审发现 `RiskLevel` 只实现了 `__lt__`，缺 `__le__`/`__ge__`，
     TDD 断言 `RiskLevel.LOW < HIGH` 不完整。补齐并去重 order map。
  2. `2c93ddd`：评审发现 PatternGuardrail 可被 `rm -rf /foo`（flag 顺序）、
     `rm  -rf`（双空格）、`\rm -rf`（长形式）绕过。加固正则并补绕过用例。
  3. `255b8d0`：两阶段评审（spec 合规 → 代码质量）发现：审批 approved 后
     `mark_executed` 路径在 loop 里未接；guardrail/tool 抛异常未 fail-closed；
     `hitl.contains` 缺失；空 pipeline 返回 deny 不符合语义。逐一修复。
- **教训**：治理机制的"确定性"要求 guardrail 对任何输入都必须给出可预测
  结果——测试要覆盖"绕过形态"，否则护栏形同虚设。

---

## Phase 2 · 真实 LLM / WebUI / 凭据 / 分发（2026-07-16 ~ 07-17，inline）

| Task | Commit | 说明 |
|---|---|---|
| T1 依赖 | `006cc6b` | httpx/fastapi/uvicorn/keyring |
| T2 真实 provider | `ac5e909` | OpenAI + Anthropic（raw httpx，无 SDK） |
| T3 HumanApprove | `4c1b597` | 注入式 resolver + 超时 fail-closed |
| T4 loop 生产化 | `54e0433` | assistant message + 记忆上下文 |
| T5 凭据存储 | `6e4fa55` | keyring 后端（可注入） |
| T6 CLI | `e24977d` | config set-key/status/clear-key + serve |
| T7 FastAPI 服务 | `406c7ab` | WS 事件流 + audit REST |
| T8 前端 | `c835e10` | linear-app 风格单页 |
| T9 分发 | `2386f34` | Dockerfile + CI + README |
| T10 真实工具 | `298acd0` | read/write/list/shell/tests/search |
| T11 WS 审批桥 | `6dd086f` | HumanApprove ↔ WebSocket |
| T12 serve 接线 | `0eb603f` | 真实 LLM + config + HumanApprove |

- **技能**：`executing-plans` + `test-driven-development`。
- **关键技术约束**：所有新代码必须可离线测试——provider 用
  `httpx.MockTransport`，凭据用 fake keyring，HITL 用 fake resolver，
  server 用 FastAPI TestClient。真实 key 永不进测试/日志/代码。
- **教训**：`HumanApprove` 与 loop 之间必须有一个可注入的 resolver 接口，
  否则"超时→拒绝"无法在单测里确定性地复现。设计成
  `resolver(action, result) -> Approval` 后，测试只需传一个 `asyncio.sleep`
  的 resolver 即可验证 fail-closed。

---

## Phase 2.5 · 前端 provider/model 选择（2026-08-06，SDD subagent 驱动）

> 此轮严格走 **subagent-driven-development**：每个 task 派一个新鲜
> subagent 在独立 worktree 分支 `feat/scaffold-types` 上完成，TDD 红绿，
> 两阶段评审（spec 合规 → 代码质量），最后 merge 回 main。

### L-2.5.1 · brainstorming（轻量）+ writing-plans
- **时间**：2026-08-06 14:46–14:49
- **产出**：设计文档 `da448c5`、实现计划 `319c0aa`。
- **人工决策**：明确"provider/model 选择仅作用于当前 WS 会话，绝不写回
  `sentinel.yaml`；浏览器不做 key 录入；模型列表为后端静态注册表，不实时
  调 provider 接口"。

### L-2.5.2 · Task 1：模型注册表 + GET /models
- **技能**：`subagent-driven-development` + `test-driven-development`
- **时间**：2026-08-06 14:55
- **subagent 输出**：commit `4867140`。TDD 证据：
  - RED：`ImportError: cannot import name 'MODEL_REGISTRY'`
  - GREEN：`tests/test_server.py` 6 passed；全量 142 passed（基线 140，无回归）
- **两阶段评审**：spec 合规 ✓（/models 返回形状与前端需求一致）；代码质量 ✓
  （命名、结构沿用现有路由模式，无过度设计）。

### L-2.5.3 · Task 2：session-scoped llm_builder
- **时间**：2026-08-06 14:58
- **subagent 输出**：commit `be135a7`。
- **关键点**：任务消息携带 `provider`/`model` 时经 `llm_builder(provider,
  model)` 构建真实 LLM；builder 抛异常 → 发 `Error` 事件 + `SessionComplete`
  且不跑 loop。测试注入 fake builder（含抛异常的 builder）。

### L-2.5.4 · Task 3：CLI 接线
- **时间**：2026-08-06 15:02
- **subagent 输出**：commit `43103d1`。
- **人工干预**：评审时确认保留懒加载 import（`build_server_app` 内 import
  fastapi），避免模块级副作用；`build_server_app` 缺 key 时快速失败并给
  `config set-key` 提示。

### L-2.5.5 · Task 4：前端 provider/model 选择器
- **时间**：2026-08-06 15:05
- **subagent 输出**：commit `53ac721`。
- **验证**：`/models` 拉取 + 级联 select + 任务消息携带选择 + Error 事件
  红色渲染。前端无 JS 测试框架，靠后端 WS 测试 + 手动验证。

### L-2.5.6 · 两阶段评审 → 最终修复 → merge
- **时间**：2026-08-06 15:13–15:19
- **评审发现（Minor）**：T4 的 Error 分支用 `innerHTML`（XSS 隐患，计划继承
  的既有风格）；`loadModels()` 与 Send 存在竞态且 fetch 无 `.catch`；T2 的
  Error 事件原样转发 `str(e)`；T4 有死 import。
- **subagent 修复**：commit `77483cc`（改 `textContent`、修竞态 + 加
  `.catch`、删死 import、补 ValueError 捕获）。
- **合并**：`2a72c61` merge feat/scaffold-types → main。合并后全量 147 passed。
- **教训**：前端 XSS 属于"计划内继承的房屋风格"，但最终评审仍要求修正——
  两阶段评审的价值就在于它不因为是"计划就这样"就放过。

---

## L-3 · 最终交付补全（2026-08-09）

- **缺口发现**（对照通用要求 §五 清单自查）：
  1. 本地 main 领先 origin/main 23 个 commit 未推送；
  2. `SPEC_PROCESS.md`、`AGENT_LOG.md`、`REFLECTION.md` 缺失；
  3. PLAN 文件 checkbox 全部未标记完成、无 commit hash；
  4. README 缺「目录结构 / 已知限制 / 安全边界」等必需章节；
  5. CI 只跑 pytest，容器分发未在 CI 中构建镜像；
  6. 无线上部署 URL。
- **已执行**：
  - `git push origin main`（255b8d0..2a72c61）；
  - 补写本文档与 `SPEC_PROCESS.md`、`REFLECTION.md`；
  - 更新 PLAN 完成标记与 commit hash；
  - README 补章节（目录结构 / 已知限制 / 安全边界 / 部署）；
  - CI 增加镜像构建 job（`build-image`），并让 GHCR 推送在配置了
    `GHCR_PAT` secret 时启用；
  - 这些修复在独立分支 `docs/final-deliverables` 上提交（PR 工作流）。
- **人工决策（部署与镜像推送）**：本机网络仅放行 GitHub / fly.io，
  Docker Hub 及镜像站不可达，且无云平台凭据。按 owner 决定，公网部署与
  GHCR 推送由 owner 稍后自行完成；README 已写好部署步骤并留出
  `<deployed-url>` 占位。CI 的 `build-image` 步骤可在 GitHub 环境正常
  验证 Dockerfile，不受本机网络限制。
- **教训**：把"push 到远程、CI 通过、部署可访问"当作验收的一部分，而不是
  实现完成后才想起——这是评审清单自查暴露的盲区。凭据与公网访问属于
  owner 环境，无法由自动化替 owner 完成，应在 README 中显式留出交接位。

---

*End of AGENT_LOG.md.*
