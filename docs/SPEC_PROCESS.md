# Sentinel — SPEC_PROCESS.md（过程文档）

> *Spec-Driven, Subagent-Built, Human-Owned.*
>
> 本文件记录与 Superpowers 协作生成 SPEC 与 PLAN 的过程，以及用"陌生"智能体
> 冷启动试运行所得的客观证据（通用要求 §4.4 / §4.5）。

---

## 1. 过程概览

本项目选用 **OpenCode + Superpowers** 作为开发工具链。整个规约工作分两轮：

1. **Phase 0（主项目 brainstorming）**：从模糊想法"做一个 Coding Agent
   Harness"出发，经多轮问答收敛为 `docs/SPEC.md`（含 §A.5 领域与机制设计），
   再由 `writing-plans` 产出 `docs/PLAN.md`（Phase 1）与
   `docs/PLAN-PHASE-2.md`（Phase 2）。
2. **Phase 2.5（增量小功能 brainstorming）**：为 WebUI 增加"LLM
   provider/model 选择"这一较小功能，单独走了一次轻量 brainstorming，
   产出 `docs/superpowers/specs/2026-08-06-frontend-model-selection-design.md`
   与对应 plan。

---

## 2. Brainstorming 关键节点

### 2.1 智能体追问过的好问题

以下是 brainstorming 过程中智能体提出、并确实推动设计的关键问题：

1. **"你要交付的是'再造一个 harness'，还是一个'在现成框架上做配置'的
   应用？"**
   这是最重要的一问。我最初的设想偏向"做一个带 WebUI 的 agent 应用"。
   智能体引导我重读了项目 A 文件 §A.4，明确交付物必须是**自研 harness
   内核**（主循环、工具分发、治理、反馈、记忆、配置），而不是在
   LangChain / CrewAI 之上做配置。这一问直接决定了项目的一切——技术选型、
   目录结构、测试策略都因此改变。

2. **"六个维度都要有，但哪个做深？"**
   我原本打算六个维度均衡推进。智能体建议选**治理（governance）**作为
   deep dimension，理由是：它最代码密集、最确定性、最可单测，也最能满足
   §A.4-C"移除真实 LLM 后仍可单测验证"的硬标准。我采纳了这一建议。

3. **"冷启动试运行时，第二个 agent 会不会因为 SPEC 里没写清 action 解析
   格式而卡住？"**
   这促使我在 SPEC §3.1 中把 `Action` 的数据结构（tool/args/raw_source/
   turn_id）和 loop 的事件类型逐一写死，而不是留给实现者发挥。

4. **"keyring 不可用时怎么办？"**
   我最初只写了"用 OS keyring"。智能体追问后备路径，促使我在 SPEC §3.8 /
   §7.1 补上"加密文件 + 主密码"回退，并在 SPEC §4.2 写清威胁模型。

### 2.2 让我修正原设想的提问

- **"你真的需要 Docker 沙箱吗？"** 我最初把 Docker 沙箱列为必选项。智能体
  指出 Phase 1（mock-LLM 内核）不应依赖 Docker，否则确定性单测无法在 CI
  里离线跑。这让我把架构拆成两阶段：Phase 1 用 `InProcessSandbox` 做内核，
  Phase 2 再把 Docker 作为分发形态。这是本项目最重要的范围修正。

---

## 3. 至少 3 轮关键迭代（节选与决策）

### 迭代 1：从"agent 应用"到"harness 内核"

- **节选**：
  > 我："我想做一个带网页界面的 AI 编程助手。"
  > 智能体："按项目 A 文件，你要交的不是'助手'，而是一个 harness。
  >   助手是 LLM + harness 的产品化，而你的评分点是 harness 本身。要不要
  >   把'看着 agent 工作 + 人工审批危险动作'作为使用场景，而核心交付是
  >   内核？"
- **决策**：采纳。把 WebUI 降级为"transport/presentation layer"（SPEC §3.7），
  明确"它不含任何 harness 逻辑"，核心是 `agent_loop` 与治理机制。

### 迭代 2：治理维度深入 vs 六维度均衡

- **节选**：
  > 智能体："六个维度都要有最低实现，但 main contribution 建议选治理。
  >   为什么？看 §A.4-B/C：反馈信号和危险动作拦截必须是确定性代码。治理
  >   是天然的代码形式——`guardrail(action)` 返回 `Deny`，每次都成立，可
  >   用单测验证。记忆做深了就得自研向量检索，工作量大且容易被判为'接现成
  >   memory'。"
- **决策**：采纳治理作为 deep dimension。SPEC §9 整节为治理展开：4 个
  纯函数 guardrail + GuardrailPipeline + ApprovalPolicy（注入式）+ HITL
  状态机 + append-only audit。这也是 §A.6 机制演示 ①③ 的主体。

### 迭代 3：冷启动暴露 SPEC 缺口后的修订

- **背景**：见 §4。第二个 agent 在"工具失败如何回灌""审批拒绝后 audit 是否
  记一条"等细节上受阻。
- **决策**：对 SPEC/PLAN 做两处修订（详见 §4 的 diff）。

---

## 4. 冷启动试运行（通用要求 §4.5 的客观证据）

### 4.1 设置

- **主开发智能体**：OpenCode（含 Superpowers 全流程）。
- **第二个智能体**：独立会话，使用不同的 agent 类型（冷启动试运行时指定
  一个与主开发 agent 类型不同的 worker），全新 session，未导入任何先前会话
  或 memory，仅提供 `docs/SPEC.md` + `docs/PLAN.md` 文本，无任何口头补充。
- **任务指派**：从 PLAN 中自主选择 Phase 1 的 Task 13（agent 主循环）与
  Task 16（机制演示）推进，并明确"遇到不确定之处即暂停询问，而非凭猜测
  继续"。

### 4.2 第二个 agent 在哪里暂停并提问

1. **在 `agent_loop` 的返回值形态上暂停**：第二个 agent 对"事件流中
   `FeedbackReceived` 的 `failures` 字段到底放 `Failure` 对象还是字符串
   列表"不确定。SPEC §3.1 只写了"yield `FeedbackReceived`"，没写 payload
   结构 → **SPEC 缺陷**。
2. **在"审批被拒后是否要写一条 audit entry"上暂停**：第二个 agent 发现
   SPEC §3.3 说"Every decision is appended to the audit log"，但 §9.4 的
   状态机图里 `Denied → Skipped` 没有明确说会写 audit。实现存在两种解读 →
   **SPEC 缺陷**。
3. **在 `run_shell` 非零退出是"信息"还是"错误"上提问**：第二个 agent
   想抛异常，而 SPEC §3.2 已写明"non-zero is information"，这一处 SPEC 写
   得清楚，agent 没有误读 → **spec 正确的反例**。

### 4.3 暴露的 spec 缺陷与修订（修订前后关键 diff）

**修订 1 — `FeedbackReceived` 的 payload 结构。**
修订前 SPEC §3.1 无 payload 说明；修订后明确：

```diff
-- Output: an event stream: ... `FeedbackReceived`, `TurnComplete`, `Stopped`.
++ Output: an event stream: ... `FeedbackReceived` (data: `{"passed": bool|None,
++          "failures": [str, ...]}` — `failures` 为 `FailureKind` 的取值列表),
++          `TurnComplete`, `Stopped`.
```

（`PLAN.md` Task 13 的 loop 测试同步把断言写为 `e.data["failures"]`。）

**修订 2 — 审批拒绝必须落 audit 记录。**
修订前 §9.4 状态机对 `Denied` 分支未注明 audit；修订后明确：

```diff
-- Timeout → `Denied` (fail-closed)
++ Timeout → `Denied` (fail-closed); 每条 `Denied`/`Skipped` 都会追加一条
++ outcome="skipped" 的 AuditEntry（§9.5），可在 WebUI audit 视图中复核。
```

对应实现中 `loop.py` 在拒绝分支追加 `AuditEntry(..., outcome="skipped")`，
并由 `test_demo_hitl_depth_timeout` 断言 `outcome == "skipped"` 记录存在。

### 4.4 解读分歧：spec 写错还是 agent 读错

- **分歧 1**（action 解析格式）：第二个 agent 一度把 `run_shell` 的 cmd
  参数读成列表而不是字符串。经核，SPEC §3.1 的 `Action.args` 是 `dict`，
  PLAN 的示例均为字符串，是 agent 读错；**spec 无需修订**。
- **分歧 2**（`max_turns` 到达时事件）：agent 认为应抛异常；SPEC 明确
  "Stop on ... `max_turns`"，是 agent 误读，spec 正确。

### 4.5 产出与预期差距

第二个 agent 独立完成的 Task 13 需要 2 轮提问澄清、额外约 1.5 小时（vs
主流程同 task 约 40 分钟），且首版 loop 在"审批拒绝分支不写 audit"上
与主 agent 实现不一致——这正是修订 2 的由来。差距集中在 SPEC 未写清的
event payload 与 audit 语义，而非核心设计。

### 4.6 小结

冷启动验证的价值在于：它把"我和主 agent 在 brainstorming 中沉淀的隐性
上下文"变成显式检查项。两处修订都是"为了让第二个 agent 不再卡住"而
做出的，客观上提升了 SPEC 的完整性。

---

## 5. 哪些建议来自 AI 且被采纳 / 被推翻

### 采纳（AI 提出）

1. **治理作为 deep dimension**（§3 迭代 2）。
2. **两阶段拆分**：Phase 1 mock 内核（InProcessSandbox）+ Phase 2 真实
   LLM/WebUI/Docker（§2.2）。
3. **loop 用 async-generator 事件流**：测试（MockLLM+AutoApprove）与生产
   （真实 LLM+HumanApprove）共用同一份 `agent_loop` 代码，仅注入不同
   collaborator。这一条让"核心机制可用 mock 单测"成为结构上的必然。
4. **ApprovalPolicy 注入式协议**：`AutoApprove`/`AutoDeny`/`ThresholdApprove`
   /`HumanApprove` 同为 `ApprovalPolicy` 的实现，使 HITL 在测试里完全离线。

### 推翻或修正（我否决）

1. **"记忆做深，用向量库 + embedding"**：我否决了该建议，因为 (a) Phase 1
   无网络，无法跑 embedding；(b) §A.4-D 提示接现成 memory 容易被判为
   "内容物"。改为自研 SQLite + TF-IDF 检索（§3.5）。
2. **"WebUI 也用 Open Design 完整搭建 dashboard"**：我修正为最小前端
   （linear-app 风格的单页 index.html），理由是 WebUI 不是 main contribution，
   不应挤占治理深度的时间预算。SPEC §3.7 明确 WebUI 不含 harness 逻辑。
3. **"Phase 1 就上 Docker 沙箱"**：被两阶段拆分取代（见上）。

---

## 6. 对 brainstorming 技能的反思

**做得好的地方：**
- 追问式引导是有效的：它把我的"想要一个 AI 编程助手"重构成"交付一个
  harness 内核"，这是本项目成败的转折点。
- 它会主动用项目文件（A 文件）约束我的想法，而不是顺着我的初稿写——这
  避免了"包装现成框架"的踩坑。

**让我不满的地方：**
- 交互轮次偏多，有时在"该做深"的维度（如治理的 HITL 状态机细节）反复
  确认，而在"不该做深"的地方（如记忆）也给同样篇幅。对我这种已经有方向
  的用户，能识别"已知/未知"并裁剪追问会更高效。
- 它没有主动提醒"冷启动试运行必须在写实现前做"——是我事后补的。若它能
  在 brainstorming 结束时就安排，spec 缺口会更早暴露。

---

*End of SPEC_PROCESS.md.*
