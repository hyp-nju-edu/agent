## Task 8: GuardrailPipeline (aggregation)

**Files:**
- Modify: `sentinel/core/guardrails.py` (add `GuardrailPipeline`)
- Modify: `tests/test_guardrails.py` (add cases)

**Interfaces:**
- Produces: `GuardrailPipeline.check(action, ctx) -> GuardrailResult` (aggregates: any Deny → Deny; else any RequireApproval → RequireApproval with highest risk; else Allow).

- [ ] **Step 1: Write the failing tests (append)**

```python
from sentinel.core.guardrails import GuardrailPipeline

def test_pipeline_deny_short_circuits():
    pipe = GuardrailPipeline([PatternGuardrail(), ScopeFenceGuardrail(workspace="/tmp/ws")])
    r = pipe.check(Action("run_shell", {"cmd": "rm -rf /"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pipeline_require_approval_when_network():
    pipe = GuardrailPipeline([PatternGuardrail(), SandboxBoundaryGuardrail()])
    r = pipe.check(Action("run_shell", {"cmd": "pip install requests"}), RunContext(task=""))
    assert r.decision == Decision.REQUIRE_APPROVAL

def test_pipeline_allow_when_safe():
    pipe = GuardrailPipeline([PatternGuardrail(), SandboxBoundaryGuardrail()])
    r = pipe.check(Action("run_shell", {"cmd": "pytest"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_pipeline_highest_risk_wins():
    pipe = GuardrailPipeline([SandboxBoundaryGuardrail(), RiskClassifierGuardrail()])
    r = pipe.check(Action("run_shell", {"cmd": "pip install x"}), RunContext(task=""))
    assert r.decision == Decision.REQUIRE_APPROVAL
    assert r.risk_level == RiskLevel.HIGH
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: FAIL with `ImportError: cannot import name 'GuardrailPipeline'`

- [ ] **Step 3: Write minimal implementation (append to `sentinel/core/guardrails.py`)**

```python
class GuardrailPipeline:
    def __init__(self, guardrails: list[Guardrail]) -> None:
        self._guardrails = list(guardrails)

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        results = [g.check(action, ctx) for g in self._guardrails]
        for r in results:
            if r.decision == Decision.DENY:
                return r
        approvals = [r for r in results if r.decision == Decision.REQUIRE_APPROVAL]
        if approvals:
            best = max(approvals, key=lambda x: x.risk_level)
            return best
        for r in results:
            if r.decision == Decision.ALLOW:
                return r
        return GuardrailResult(Decision.ALLOW, "no guardrails", RiskLevel.LOW, "pipeline")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/guardrails.py tests/test_guardrails.py
git commit -m "feat(governance): add GuardrailPipeline with deny/approve aggregation"
```

---

