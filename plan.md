# Self-Learning SQL Agent — Implementation Plan

## Context

Build a self-learning agent inspired by the NousResearch Hermes agent (memory + skill generation concepts) that iteratively improves SQL queries based on past failures. The Hermes architecture's two key ideas being adopted here are:

1. **Memory store** — persist every failure, its error type, the successful fix, and fix description in SQLite so the agent remembers across sessions.
2. **Skill files** — auto-generate and update Markdown files (with YAML frontmatter) keyed by error type; these are retrieved at query-time to give Claude reusable fix strategies.

The entry point is a `run_demo.py` script that feeds pre-written broken queries against a local SQLite sample database and shows the learning loop in action. No CLI REPL or external Postgres needed.

---

## File Structure

```
self-learning-agent/
├── agent/
│   ├── __init__.py
│   ├── core.py           # SQLLearningAgent — main agent loop
│   ├── memory.py         # MemoryStore — SQLite-backed failure/fix log
│   ├── skill_manager.py  # SkillManager — Markdown skill file I/O + retrieval
│   ├── sql_executor.py   # SQLExecutor — run queries, return result or error
│   └── classifier.py     # ErrorClassifier — map SQLite errors → error_type str
├── skills/               # Auto-generated skill Markdown files (git-ignored data)
├── data/                 # SQLite files (created at runtime)
├── run_demo.py           # Demo entry point
├── config.py             # Paths, model name, max iterations
└── requirements.txt      # anthropic, pyyaml
```

---

## Component Design

### `config.py`
Constants: `ANTHROPIC_MODEL = "claude-sonnet-4-6"`, `SKILLS_DIR`, `DATA_DIR`, `MEMORY_DB_PATH`, `SAMPLE_DB_PATH`, `MAX_ITERATIONS = 4`.

---

### `agent/sql_executor.py` — `SQLExecutor`
- `__init__(db_path)` — opens SQLite connection
- `execute(query) -> tuple[list[dict] | None, str | None]` — returns `(rows, None)` on success or `(None, error_message)` on failure
- `setup_sample_db()` — creates e-commerce schema + seed data:
  - `categories(id, name)`
  - `products(id, name, price, category_id, stock)`
  - `customers(id, name, email, created_at)`
  - `orders(id, customer_id, product_id, quantity, total, order_date)`

---

### `agent/classifier.py` — `ErrorClassifier`
Maps raw SQLite error strings to stable `error_type` keys used as skill file names:

| SQLite message pattern | error_type |
|---|---|
| `syntax error` | `syntax_error` |
| `no such table` | `no_such_table` |
| `no such column` | `no_such_column` |
| `datatype mismatch` | `type_mismatch` |
| `ambiguous column` | `ambiguous_column` |
| `UNIQUE constraint` | `constraint_violation` |
| anything else | `unknown_error` |

Single method: `classify(error_message: str) -> str`

---

### `agent/memory.py` — `MemoryStore`
SQLite DB at `data/memory.db`.

**Tables**:
```sql
CREATE TABLE query_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_query TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    fixed_query TEXT,
    fix_description TEXT,
    iterations INTEGER DEFAULT 1,
    success INTEGER DEFAULT 0,       -- 0/1
    skill_generated TEXT,            -- skill file name, if one was created
    timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE error_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_type TEXT UNIQUE NOT NULL,
    occurrences INTEGER DEFAULT 1,
    last_seen TEXT DEFAULT (datetime('now'))
);
```

**Key methods**:
- `record_failure(original_query, error_type, error_message) -> int` — inserts row, upserts error_patterns, returns row id
- `record_success(failure_id, fixed_query, fix_description, iterations, skill_generated)` — updates the row
- `get_similar_failures(error_type, limit=3) -> list[dict]` — fetch recent failures of same type for context
- `get_error_stats() -> list[dict]` — error_type + occurrences, for summary display

---

### `agent/skill_manager.py` — `SkillManager`
Reads and writes Markdown files in `skills/`. Each file is named `<error_type>.md`.

**Frontmatter schema**:
```yaml
---
name: <error_type>
description: <one-line summary>
error_types:
  - <error_type>
success_rate: 0.0          # updated each use
usage_count: 0
created_at: <ISO datetime>
last_updated: <ISO datetime>
---
```
Body: free-form Markdown with strategy, patterns, and examples — written by Claude.

**Key methods**:
- `load_skill(error_type) -> dict | None` — parse frontmatter + body, return `{meta, body}` or None
- `save_skill(error_type, description, body, existing_meta=None)` — write/overwrite file, update timestamps and usage_count
- `update_success_rate(error_type, was_success: bool)` — running average update on success_rate field
- `list_skills() -> list[dict]` — all skill metas (for display)

---

### `agent/core.py` — `SQLLearningAgent`
**Dependencies**: `SQLExecutor`, `MemoryStore`, `SkillManager`, `ErrorClassifier`, `anthropic.Anthropic`

**`improve(original_query) -> dict`** — main public method, returns:
```python
{
  "original_query": str,
  "final_query": str,
  "success": bool,
  "iterations": int,
  "error_types_seen": list[str],
  "skill_created_or_updated": str | None,
}
```

**Inner loop** (max `MAX_ITERATIONS`):
1. Execute current query via `SQLExecutor`
2. If success → record to memory, call `_maybe_generate_skill()`, return result
3. Classify error → `error_type`
4. `record_failure()` in memory; load matching skill (if any); load similar past failures
5. Build Claude prompt (see below) → call API → parse response for `<fixed_query>` and `<skill_body>`
6. If Claude returns a skill body and no skill exists yet → `save_skill()`; if skill exists → `update_success_rate()`
7. Loop with fixed query

**Claude prompt structure**:
- System: Agent role, output format instructions (XML tags `<fixed_query>`, `<fix_explanation>`, `<skill_body>`)
- User: Original query, error message, relevant skill content, 3 similar past failures (query + fix)

**`_maybe_generate_skill(error_type, fix_explanation, skill_body)`**:
If `skill_body` is non-empty, save or update the skill file.

---

### `run_demo.py`
1. `SQLExecutor.setup_sample_db()` — create `data/sample.db`
2. Define 5 intentionally broken queries:
   - Missing comma in SELECT: `SELECT name price FROM products`
   - Wrong column name: `SELECT customer_name, email FROM customers`
   - Wrong table name: `SELECT * FROM product WHERE price > 10`
   - Type mismatch in WHERE: `SELECT * FROM orders WHERE total = 'ten'`
   - Ambiguous column in JOIN: `SELECT id, name FROM customers JOIN orders ON customers.id = orders.customer_id`
3. For each query: call `agent.improve(query)`, print step-by-step output showing iterations, what failed, what was fixed, and whether a skill was created/updated
4. Print final summary: `agent.memory.get_error_stats()`, `agent.skill_manager.list_skills()`

---

## Data Flow (Single Query)

```
run_demo.py
    └─► SQLLearningAgent.improve(broken_query)
            ├── SQLExecutor.execute()          → error_message
            ├── ErrorClassifier.classify()     → error_type
            ├── MemoryStore.record_failure()   → failure_id
            ├── SkillManager.load_skill()      → skill content (or None)
            ├── MemoryStore.get_similar_failures() → past examples
            ├── Anthropic API call             → fixed_query + skill_body
            ├── SQLExecutor.execute(fixed)     → success
            ├── MemoryStore.record_success()
            └── SkillManager.save_skill()      → skills/<error_type>.md
```

---

## Verification

1. **Run demo**: `ANTHROPIC_API_KEY=... python run_demo.py`
   - All 5 broken queries should be fixed within MAX_ITERATIONS
   - `skills/` directory should contain at least 3–4 `.md` files after the run
   - `data/memory.db` `query_failures` table should have 5+ rows with `success=1`

2. **Re-run demo**: On a second run, the agent should retrieve existing skills and similar past failures — Claude's prompt will be richer and fixes should land in fewer iterations (demonstrating learning).

3. **Inspect skill files**: Each `.md` should have valid YAML frontmatter and a non-empty body describing the fix strategy with an example.

4. **Manual check**: `python -c "from agent.memory import MemoryStore; m = MemoryStore('data/memory.db'); print(m.get_error_stats())"` should show error type counts.

---

## Dependencies

```
anthropic>=0.40.0
pyyaml>=6.0
```
No other third-party packages needed — SQLite and the standard library handle everything else.
