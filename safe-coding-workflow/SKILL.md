---
name: safe-coding-workflow
description: >
  A disciplined workflow for planning, executing, and verifying non-trivial code
  changes safely. Use this skill whenever the user asks for a code change that is
  hard, risky, multi-file, or ambiguous — including bug fixes, refactors, feature
  additions, dependency upgrades, migrations, performance work, or "fix this
  failing test" requests. Also use it when entering an unfamiliar codebase, when
  the blast radius of a change is unclear, or when the user asks you to "be
  careful", "don't break anything", or to explain what you changed and why.
  Do NOT skip this skill just because the change looks small — small diffs in
  unfamiliar code are where regressions hide.
compatibility: >
  Requires a shell (or equivalent file/read/edit tools). Works best with access
  to the project's test runner, linter, and version control.
---

# Safe Coding Workflow

A skill that turns "make this change" into a sequence of observable, verifiable
steps: inspect → plan → change minimally → verify → report with evidence.

Core principle: **never claim something works that you have not observed
working.** Every claim in the final report must be backed by a command you ran,
output you read, or a file you inspected. Reasoning is expressed as visible
artifacts (notes, plans, command output), not as private deliberation.

---

## When to use

Use this workflow when ANY of the following are true:

- The task touches more than one file, or you don't yet know how many files it touches.
- You are new to this codebase or this area of it.
- The change affects public APIs, data models, persistence, auth, money, concurrency, or anything user-facing.
- The task description is ambiguous, contradictory, or missing acceptance criteria.
- Tests exist and could break, or tests don't exist and should.
- The user asked for a "quick fix" in code you haven't read yet. (Especially then.)

You may abbreviate the workflow (not skip verification) only when the change is
a single-file, single-purpose edit in code you have already read this session,
with a fast test or run command available.

---

## Step-by-step workflow

### Phase 0 — Restate the task

Before touching anything, write down (in your working notes or response):

1. **Goal**: one sentence describing the desired end state.
2. **Acceptance criteria**: how you will know it's done (specific behaviors, passing tests, output).
3. **Explicit constraints**: anything the user said not to do (no new deps, keep API stable, etc.).
4. **Open questions**: anything ambiguous. Decide per the "missing information" rules below whether to ask or proceed with a stated assumption.

If you cannot state acceptance criteria, you are not ready to edit code.

### Phase 1 — Inspect before editing

Never edit a file you haven't read. Never assume structure you haven't verified.

Run a reconnaissance pass and record what you find:

```
# Layout and entry points
ls / tree (2 levels), README, docs/

# Project type, dependencies, versions
package.json / pyproject.toml / go.mod / Cargo.toml / pom.xml ...
lockfiles (to see what's actually pinned)

# How the project is built, run, and tested
Makefile, scripts section, CI config (.github/workflows, .gitlab-ci.yml)

# Conventions and constraints
linter/formatter configs, tsconfig/mypy strictness, CONTRIBUTING.md, .editorconfig

# State of the tree
git status, git log --oneline -10 (am I on a dirty tree? recent related changes?)
```

Then narrow to the task area:

- Locate the code paths involved (grep for the function/route/error message).
- Read the relevant files fully, not just the matching lines.
- Find the callers and callees of anything you plan to change (`grep -rn`, IDE-equivalent search). List them.
- Find existing tests for this area and run them **before** changing anything, so you know the baseline. A test that was already failing is not your regression — but you must know that before you edit.

Record a short written map: "The request flows A → B → C; the bug is likely in B because ...; B is called from X and Y."

### Phase 2 — Decompose into safe steps

Break the task into steps where each step:

- Has a single purpose (one behavior change, one refactor, one dependency bump — never mixed).
- Leaves the project in a working or at least buildable state.
- Is independently verifiable (a command that proves it worked).
- Is reversible (small enough to revert without archaeology).

Order steps risk-first when possible: do the investigation and scaffolding (add a failing test that reproduces the bug) before the fix, and do behavior-preserving refactors in separate steps from behavior changes.

Write the plan down as a numbered list with a verification command per step. Example:

```
1. Add failing test reproducing #142 (verify: pytest tests/test_auth.py -k expired — fails)
2. Fix token expiry comparison in auth/session.py (verify: same test passes)
3. Run full auth test suite (verify: pytest tests/test_auth.py — all pass)
4. Run linter + typecheck (verify: ruff check, mypy — clean)
```

### Phase 3 — Detect edge cases and hidden risks

Before implementing, explicitly check the task against this list and write down which apply:

- **Inputs**: empty, null/None, zero, negative, huge, malformed, wrong encoding, unicode, duplicates.
- **Boundaries**: off-by-one, inclusive vs exclusive ranges, first/last element, empty collections.
- **Time**: timezones, DST, clock skew, expiry exactly at boundary, leap days, ordering of async events.
- **Concurrency**: shared state, race on read-modify-write, idempotency of retries.
- **Persistence & migration**: old data shaped by the previous code; will existing rows/files still parse?
- **Compatibility**: public API signatures, serialized formats, config keys, CLI flags other code may depend on.
- **Error paths**: what happens when the dependency call fails, times out, returns partial data?
- **Security**: injection via the values you're now handling, secrets in logs, authz checks bypassed by a new code path.
- **Hidden callers**: dynamic dispatch, reflection, string-based imports, templates, scheduled jobs, other repos.

For each applicable risk, either handle it in the plan, cover it with a test, or explicitly note it as out of scope in the report.

### Phase 4 — Implement with safe editing rules

(See "Safe code editing rules" below.) Work step by step through the plan, running the step's verification command before moving on. If a step's verification fails, stop and fix or replan — do not stack changes on a broken state.

### Phase 5 — Verify the whole

Run the full verification checklist (below). Verification of individual steps is not sufficient; interactions between steps are where regressions live.

### Phase 6 — Report with evidence

Produce a final report in the reporting format (below). Every claim of success must cite the command and its observed result.

---

## Safe code editing rules

1. **Read before write.** Read the entire function/class you're editing and its immediate neighbors. Never edit from a grep snippet alone.
2. **Minimal diff.** Change only what the task requires. No drive-by reformatting, renaming, or "improvements" outside scope — they pollute review and hide the real change. If you notice unrelated problems, record them in the report instead of fixing them silently.
3. **Match existing conventions.** Follow the project's style, naming, error-handling patterns, and test structure, even where you'd personally choose differently.
4. **Preserve public contracts.** Don't change function signatures, API shapes, config keys, serialized formats, or exported names unless the task explicitly requires it. If you must, list every caller you updated and how you found them.
5. **No silent behavior changes.** If a fix necessarily changes observable behavior beyond the bug (error messages, ordering, defaults), call it out explicitly.
6. **No new dependencies without justification.** Prefer the standard library and existing project deps. If a new dependency is genuinely needed, state why, check its license and maintenance status, and pin the version.
7. **Never weaken safety to make things pass.** Do not delete or skip failing tests, loosen assertions, broaden `except`/`catch` blocks, disable lint rules, or add `# type: ignore` to silence errors — unless the test/rule itself is demonstrably wrong, in which case say so in the report with reasoning.
8. **No destructive operations without an explicit go-ahead.** Do not delete files/branches, run migrations against shared databases, force-push, rewrite history, or touch production systems or credentials on your own initiative.
9. **Keep the tree recoverable.** Work on a clean tree where possible; commit or checkpoint at safe boundaries so any step can be reverted alone.
10. **Handle generated and vendored code correctly.** Never hand-edit generated files (protobufs, lockfiles, build output); change the source and regenerate.
11. **Secrets stay out.** Never hardcode credentials, tokens, or user data in code, tests, fixtures, or logs.
12. **When a "simple fix" grows**, stop. If the diff is spreading beyond the plan, return to Phase 2 and replan rather than improvising.

---

## Deciding what to do next when information is missing

Classify the gap, then act:

| Gap type | Action |
|---|---|
| Answer exists in the repo (behavior, conventions, structure) | **Investigate.** Read code, run it, write a scratch test. Don't ask the user things the codebase can answer. |
| Answer exists in docs of a dependency/tool | **Look it up** (docs, changelog, source in the lockfile's pinned version). |
| Product/intent decision (which behavior is *desired*), destructive or irreversible action, scope expansion, security tradeoff | **Ask the user.** Present the options you see and your recommendation. |
| Low-stakes ambiguity where any reasonable reading is fine | **Proceed with a stated assumption.** Write the assumption in your plan and repeat it prominently in the final report so it can be corrected cheaply. |
| Blocked entirely (missing access, broken environment, cannot reproduce) | **Stop and report** exactly what you tried, what failed, and what you need — do not fabricate a workaround that pretends the blocker is gone. |

Rule of thumb: investigate facts, ask about intent, state assumptions you make, and never let an unstated assumption reach the final report.

---

## Verification checklist

Do not claim completion until every applicable item is checked, each backed by an actually executed command and observed output:

- [ ] **Baseline recorded**: pre-change test/build status was captured, so new failures are distinguishable from pre-existing ones.
- [ ] **The change is exercised**: at least one test or manual run demonstrably executes the new/changed code path (not just "tests pass" — tests that never touch your code prove nothing).
- [ ] **New/updated tests fail without the fix** (for bug fixes: you saw the test fail on the old code, then pass on the new).
- [ ] **Relevant test suite passes**: run the project's own test command (from CI config or scripts), not a guessed one.
- [ ] **Build/compile/typecheck passes** with the project's real configuration.
- [ ] **Linter/formatter passes**, using the project's config.
- [ ] **Edge cases from Phase 3** are covered by tests or explicitly noted as out of scope.
- [ ] **Diff reviewed**: read the full `git diff` yourself; confirm no unintended files, debug prints, commented-out code, TODO placeholders, or secrets.
- [ ] **Callers audited**: every caller of changed interfaces was found and updated or confirmed unaffected.
- [ ] **No verification theater**: no skipped/disabled tests, loosened assertions, or suppressed warnings introduced to make checks green.
- [ ] **Pre-existing failures listed**: anything that was already broken before your change is documented as such, with evidence of the baseline run.

If an item cannot be verified in this environment (e.g., no test runner available), the report must say so explicitly rather than implying it passed.

---

## Reporting format

Final reports use this structure:

```markdown
## Summary
One paragraph: what was asked, what was done, current status
(✅ complete / ⚠️ complete with caveats / ❌ blocked).

## Changes
- `path/to/file.py` — what changed and why (one line per file)

## Evidence
For each verification claim: the command run and the observed result.
Quote the decisive lines of output, not walls of logs.

## Assumptions & decisions
Assumptions made where information was missing; alternatives considered
and why the chosen approach won.

## Risks & out of scope
Known limitations, edge cases deliberately not handled, pre-existing
issues noticed but not fixed, and anything the reviewer should look at
extra carefully.

## Suggested follow-ups (optional)
Improvements observed but intentionally not made.
```

Rules for reports:

- Every "passes" / "works" / "fixed" claim links to an Evidence entry.
- Distinguish clearly between *verified* ("ran X, saw Y") and *expected* ("should also work for Z, not tested here").
- Report failures and partial completion honestly and prominently — a precise "blocked" report is a success; a vague "done" that isn't is a failure.

---

## Examples of good final reports

### Example 1 — Bug fix, fully verified

```markdown
## Summary
Fixed #142: sessions with tokens expiring exactly at the request timestamp were
accepted instead of rejected. Root cause was an inclusive comparison in
`Session.is_valid`. Status: ✅ complete.

## Changes
- `auth/session.py` — changed `expires_at >= now` to `expires_at > now` in `is_valid`
- `tests/test_session.py` — added `test_token_expiring_at_boundary` reproducing the bug

## Evidence
- Baseline: `pytest tests/ -q` before changes → 214 passed (no pre-existing failures)
- Repro: new test on unmodified code → `FAILED tests/test_session.py::test_token_expiring_at_boundary — AssertionError: expected invalid`
- Fix verified: `pytest tests/test_session.py -q` → 31 passed
- Full suite: `pytest tests/ -q` → 215 passed
- Callers audited: `grep -rn "is_valid" --include="*.py"` → 3 call sites
  (middleware.py:88, admin/views.py:41, tasks/cleanup.py:19); all treat a False
  return as "reject/clean up", so the stricter boundary is safe for all.
- Lint/type: `ruff check .` clean; `mypy auth/` clean.

## Assumptions & decisions
- Treated "expires exactly now" as expired, matching the RFC 7519 `exp` claim
  semantics referenced in `auth/README.md`.

## Risks & out of scope
- `tasks/cleanup.py` will now purge boundary sessions one tick earlier; behavior
  change is negligible but noted.
- Did not touch refresh-token expiry (`auth/refresh.py`), which has the same
  inclusive comparison — flagged as follow-up rather than expanding scope.

## Suggested follow-ups
- Apply the same boundary fix + test to `RefreshToken.is_valid`.
```

### Example 2 — Blocked, reported honestly

```markdown
## Summary
Attempted to upgrade `libfoo` 2.x → 3.x. Upgrade compiles, but 3.x removed the
streaming API used in `ingest/reader.py` and the replacement requires an async
runtime this codebase doesn't use. Stopping for a design decision rather than
introducing an event loop unilaterally. Status: ❌ blocked (no changes committed;
tree restored to baseline).

## Changes
None retained. Exploratory branch `spike/libfoo-3` contains the partial port
for reference.

## Evidence
- Baseline: `make test` on main → 96 passed
- After bump to 3.1.0: `make build` → 7 compile errors, all
  `foo.stream_reader` removals (full list in spike branch commit message)
- Migration guide (libfoo CHANGELOG v3.0.0) confirms `stream_reader` was
  replaced by async-only `foo.aio.reader`
- Verified rollback: `git status` clean on main; `make test` → 96 passed

## Assumptions & decisions
- Chose not to wrap the async API in `asyncio.run()` inside the hot ingest loop:
  a quick benchmark on the spike branch showed ~4x slowdown on
  `tests/perf/test_ingest_throughput.py`.

## Risks & out of scope
- Staying on 2.x: 2.19 receives security fixes until 2027-03 per upstream policy,
  so there is no immediate pressure.

## Suggested follow-ups (decision needed)
1. Adopt async ingest properly (larger refactor, est. multi-day), or
2. Pin `libfoo <3` and revisit when the async migration is scheduled.
Recommendation: option 2 now, schedule option 1.
```

### Example 3 — Complete with caveats

```markdown
## Summary
Added CSV export to the reports page as requested. Status: ⚠️ complete with
caveats — feature works and is tested, but one pre-existing unrelated test
failure exists on main, and locale-specific number formatting is out of scope.

## Changes
- `reports/export.py` — new `to_csv(report)` using stdlib `csv` (no new deps)
- `reports/views.py` — added `/reports/<id>/export.csv` route, permission-gated
  with the existing `can_view_report` check
- `tests/test_export.py` — 6 tests: happy path, empty report, unicode fields,
  fields containing commas/quotes/newlines, permission denied

## Evidence
- Baseline: `pytest -q` on main → 1 pre-existing failure
  (`test_email_digest_timezone`, also fails on untouched main — evidence: ran on
  clean checkout of `main@a1b2c3d`)
- After change: `pytest -q` → same single pre-existing failure; all 6 new tests pass
- Injection edge case: verified fields starting with `=` are prefixed per OWASP
  CSV-injection guidance; covered by `test_formula_injection_escaped`
- `ruff check .` and `mypy reports/` clean

## Assumptions & decisions
- Assumed UTF-8 with BOM for Excel compatibility, matching the existing XLSX
  exporter's comment in `reports/xlsx.py:12`. Easy to change if undesired.

## Risks & out of scope
- Numbers are exported in machine format (`1234.5`), not locale format —
  not requested, noted for the reviewer.
- Pre-existing `test_email_digest_timezone` failure is unrelated and untouched.
```
