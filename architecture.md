# Self-Learning SQL Agent — Architecture

## Dataflow Diagram — Program Execution

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  run_demo.py                                                                    │
  │                                                                                 │
  │  BROKEN_QUERIES = [                                                             │
  │    "SELECT name, price, FROM products",   ◄── syntax_error                     │
  │    "SELECT name, pric FROM products",     ◄── no_such_column                   │
  │    "SELECT * FROM product WHERE ...",     ◄── no_such_table                    │
  │    "SELECT customer_name ... FROM ...",   ◄── no_such_column                   │
  │    "SELECT id, name FROM customers ...",  ◄── ambiguous_column                 │
  │  ]                                                                              │
  └───────────────────────────────┬─────────────────────────────────────────────────┘
                                  │
                    original_query: str
                                  │
                                  ▼
  ┌───────────────────────────────────────────────────────────────────────────────────┐
  │  SQLLearningAgent.improve()   [agent/core.py]                                     │
  │                                                                                   │
  │  state:                                                                           │
  │    current_query     = original_query                                             │
  │    failure_id        = None                                                       │
  │    error_types_seen  = []                                                         │
  │    iteration         = 1 .. MAX_ITERATIONS (4)                                    │
  │                                                                                   │
  │  ┌──────────────────────────────────────────────────────────────────────────┐    │
  │  │  ITERATION LOOP                                                          │    │
  │  │                                                                          │    │
  │  │   current_query: str                                                     │    │
  │  │        │                                                                 │    │
  │  │        ▼                                                                 │    │
  │  │   ┌──────────────────────┐   query: str    ┌──────────────────────┐     │    │
  │  │   │    SQLExecutor       │ ──────────────► │   data/sample.db     │     │    │
  │  │   │  .execute(query)     │ ◄────────────── │   (SQLite)           │     │    │
  │  │   └──────────┬───────────┘  rows: list[dict]│ categories          │     │    │
  │  │              │              or error: str   │ products             │     │    │
  │  │              │                              │ customers            │     │    │
  │  │        ┌─────┴──────┐                       │ orders               │     │    │
  │  │        │            │                       └──────────────────────┘     │    │
  │  │     error=None   error=str                                               │    │
  │  │        │            │                                                    │    │
  │  │        │            ▼                                                    │    │
  │  │        │   ┌──────────────────────┐                                     │    │
  │  │        │   │  ErrorClassifier     │                                     │    │
  │  │        │   │  .classify(error)    │                                     │    │
  │  │        │   │                      │  error_type: str                    │    │
  │  │        │   │  "syntax error"      │  ──────────────                     │    │
  │  │        │   │    → syntax_error    │  syntax_error                       │    │
  │  │        │   │  "no such table"     │  no_such_table                      │    │
  │  │        │   │    → no_such_table   │  no_such_column                     │    │
  │  │        │   │  "no such column"    │  type_mismatch                      │    │
  │  │        │   │    → no_such_column  │  ambiguous_column                   │    │
  │  │        │   │  "ambiguous column"  │  unknown_error                      │    │
  │  │        │   │    → ambiguous_col.. │                                     │    │
  │  │        │   └──────────┬───────────┘                                     │    │
  │  │        │              │ error_type: str                                  │    │
  │  │        │              ▼                                                  │    │
  │  │        │   ┌──────────────────────┐  (original_query,    ┌───────────┐  │    │
  │  │        │   │  MemoryStore         │   error_type,        │data/      │  │    │
  │  │        │   │  .record_failure()   │ ──────────────────►  │memory.json│  │    │
  │  │        │   │                      │   error_message)     │           │  │    │
  │  │        │   │  returns failure_id  │                      │failures:[]│  │    │
  │  │        │   └──────────┬───────────┘                      │error_     │  │    │
  │  │        │              │ failure_id: int                   │patterns:{}│  │    │
  │  │        │              ▼                                   └─────▲─────┘  │    │
  │  │        │   ┌──────────────────────┐                            │         │    │
  │  │        │   │  SkillManager        │  error_type: str           │         │    │
  │  │        │   │  .load_skill(        │ ──────────────►  reads     │         │    │
  │  │        │   │    error_type)       │                skills/     │         │    │
  │  │        │   │                      │  {meta, body}  <error>.md  │         │    │
  │  │        │   │  None on first run   │ ◄──────────────            │         │    │
  │  │        │   └──────────┬───────────┘                 ┌──────────┴──────┐  │    │
  │  │        │              │ skill: {meta,body} | None    │   skills/       │  │    │
  │  │        │              ▼                              │ syntax_error.md │  │    │
  │  │        │   ┌──────────────────────┐                 │ no_such_col.md  │  │    │
  │  │        │   │  MemoryStore         │  error_type: str│ no_such_tbl.md  │  │    │
  │  │        │   │  .get_similar_       │ ──────────────► │ ambiguous_col.md│  │    │
  │  │        │   │    failures()        │                 └─────────────────┘  │    │
  │  │        │   │                      │  list[{                              │    │
  │  │        │   │  [] on first run     │   original_query,                   │    │
  │  │        │   │  [{...}] on run 2+   │ ◄─ fixed_query,                     │    │
  │  │        │   └──────────┬───────────┘   fix_description                   │    │
  │  │        │              │ similar: list[dict]          }]                  │    │
  │  │        │              ▼                                                  │    │
  │  │        │   ┌──────────────────────────────────────────────────────┐     │    │
  │  │        │   │  _build_prompt()                                     │     │    │
  │  │        │   │  ──────────────────────────────────────              │     │    │
  │  │        │   │  ## Database Schema                                  │     │    │
  │  │        │   │  categories(id, name), products(id, name, ...)       │     │    │
  │  │        │   │                                                      │     │    │
  │  │        │   │  ## Original Query                                   │     │    │
  │  │        │   │  SELECT name, pric FROM products                     │     │    │
  │  │        │   │                                                      │     │    │
  │  │        │   │  ## Error                                            │     │    │
  │  │        │   │  Type: no_such_column                                │     │    │
  │  │        │   │  Message: no such column: pric                       │     │    │
  │  │        │   │                                                      │     │    │
  │  │        │   │  ## Relevant Skill       ← injected if exists        │     │    │
  │  │        │   │  ## Similar Past Fixes   ← injected if exists        │     │    │
  │  │        │   └──────────────────────────────┬───────────────────────┘     │    │
  │  │        │                                  │ prompt: str                 │    │
  │  │        │                                  ▼                             │    │
  │  │        │   ┌──────────────────────────────────────────────────────┐     │    │
  │  │        │   │  Anthropic API  (claude-sonnet-4-6)                  │     │    │
  │  │        │   │  messages.create(system=..., messages=[prompt])      │     │    │
  │  │        │   └──────────────────────────────┬───────────────────────┘     │    │
  │  │        │                                  │ response: str               │    │
  │  │        │                                  ▼                             │    │
  │  │        │   ┌──────────────────────────────────────────────────────┐     │    │
  │  │        │   │  _extract() — parse XML tags                         │     │    │
  │  │        │   │  ──────────────────────────────                      │     │    │
  │  │        │   │  fixed_query    ← <fixed_query>...</fixed_query>     │     │    │
  │  │        │   │  explanation    ← <fix_explanation>...</..>          │     │    │
  │  │        │   │  skill_body     ← <skill_body>...</skill_body>       │     │    │
  │  │        │   └──────┬──────────────────────┬────────────────────────┘     │    │
  │  │        │          │ fixed_query: str      │ skill_body: str              │    │
  │  │        │          │                       ▼                             │    │
  │  │        │          │          ┌─────────────────────────┐               │    │
  │  │        │          │          │  SkillManager           │               │    │
  │  │        │          │          │  .save_skill() or       │  writes       │    │
  │  │        │          │          │  .update_success_rate() │ ──────────►   │    │
  │  │        │          │          └─────────────────────────┘ skills/*.md   │    │
  │  │        │          │                                                     │    │
  │  │        │          └──────────────────────────────────────────────────► │    │
  │  │        │                          current_query = fixed_query           │    │
  │  │        │                          loop continues ──────────────────────►│    │
  │  │        │                                                                │    │
  │  │     success                                                             │    │
  │  │        │                                                                │    │
  │  │        ▼                                                                │    │
  │  │   ┌──────────────────────┐  (failure_id, fixed_query,  ┌───────────┐   │    │
  │  │   │  MemoryStore         │   explanation, iterations,  │data/      │   │    │
  │  │   │  .record_success()   │ ──────────────────────────► │memory.json│   │    │
  │  │   └──────────────────────┘   skill_name)               └───────────┘   │    │
  │  │                                                                         │    │
  │  └─────────────────────────────────────────────────────────────────────────┘    │
  │                                                                                   │
  │  returns dict {                                                                   │
  │    original_query, final_query, success: bool,                                    │
  │    iterations: int, rows_returned: int,                                           │
  │    error_types_seen: list[str], skill_created_or_updated: str | None              │
  │  }                                                                                │
  └───────────────────────────────────────────────────────────────────────────────────┘
                                  │
                    result: dict
                                  │
                                  ▼
  ┌───────────────────────────────────────────────────────────────────────────────────┐
  │  run_demo.py  — _print_result()                                                   │
  │                                                                                   │
  │  Query 2  [SUCCESS]  (1 iteration)                                                │
  │    Original : SELECT name, pric FROM products                                     │
  │    Fixed    : SELECT name, price FROM products                                    │
  │    Errors   : no_such_column                                                      │
  │    Skill    : skills/no_such_column.md  (created)                                 │
  │    Rows     : 4                                                                   │
  └───────────────────────────────────────────────────────────────────────────────────┘
```

## Component Overview

```
                        ┌─────────────────┐
                        │   run_demo.py   │
                        │  (5 broken SQL  │
                        │    queries)     │
                        └────────┬────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │    SQLLearningAgent    │
                    │      core.py           │
                    └──┬──────┬──────┬──────┘
                       │      │      │      │
           ┌───────────┘  ┌───┘  ┌───┘  ┌──┘
           ▼              ▼      ▼      ▼
   ┌──────────────┐  ┌─────────┐ ┌──────────┐ ┌─────────────┐
   │ SQLExecutor  │  │ Error   │ │ Memory   │ │   Skill     │
   │sql_executor  │  │Classify │ │  Store   │ │  Manager    │
   │──────────────│  │classif. │ │memory.py │ │skill_mgr.py │
   │execute()     │  │─────────│ │──────────│ │─────────────│
   │setup_sample  │  │classify │ │record_   │ │load_skill() │
   │  _db()       │  │  ()     │ │failure() │ │save_skill() │
   │get_schema()  │  └────┬────┘ │record_   │ │update_      │
   └──────┬───────┘       │      │success() │ │success_rate │
          │               │      │get_simi- │ │list_skills()│
          │               │      │lar_fail()│ └──────┬──────┘
          ▼               │      │get_stats │        │
   ┌─────────────┐        │      └────┬─────┘        │
   │data/sample  │        │           │               │
   │   .db       │        │           ▼               ▼
   │─────────────│        │    ┌─────────────┐  ┌──────────────┐
   │ categories  │        │    │data/memory  │  │  skills/     │
   │ products    │        │    │  .json      │  │─────────────-│
   │ customers   │        │    │─────────────│  │syntax_error  │
   │ orders      │        │    │ failures[]  │  │  .md         │
   └─────────────┘        │    │ error_      │  │no_such_col   │
                          │    │ patterns{}  │  │  umn.md      │
                          │    └─────────────┘  │no_such_table │
                          │                     │  .md         │
                          │                     │ambiguous_col │
                          │                     │  umn.md      │
                          │                     └──────────────┘
                          ▼
                  ┌───────────────┐
                  │ Anthropic API │
                  │claude-sonnet  │
                  │    -4-6       │
                  │───────────────│
                  │ diagnose &    │
                  │ fix query     │
                  │ generate      │
                  │ skill body    │
                  └───────────────┘
```

---

## Query Improvement Loop

```
  broken query
       │
       ▼
  ┌────────────────────────┐
  │  SQLExecutor.execute() │
  └────────────┬───────────┘
               │
       ┌───────┴────────┐
       │                │
    success?           fail?
       │                │
       ▼                ▼
  ┌─────────┐   ┌───────────────────────┐
  │ record  │   │ ErrorClassifier       │
  │ success │   │ .classify(error_msg)  │
  │ in      │   │ → error_type          │
  │ memory  │   └──────────┬────────────┘
  └────┬────┘              │
       │                   ▼
       │          ┌─────────────────────┐
       │          │ MemoryStore         │
       │          │ .record_failure()   │
       │          └──────────┬──────────┘
       │                     │
       │                     ▼
       │          ┌─────────────────────┐
       │          │ SkillManager        │
       │          │ .load_skill(        │
       │          │   error_type)       │
       │          │ → skill md or None  │
       │          └──────────┬──────────┘
       │                     │
       │                     ▼
       │          ┌─────────────────────┐
       │          │ MemoryStore         │
       │          │ .get_similar_       │
       │          │   failures()        │
       │          │ → past fixes        │
       │          └──────────┬──────────┘
       │                     │
       │                     ▼
       │          ┌─────────────────────┐
       │          │  Claude prompt      │
       │          │  ─────────────────  │
       │          │  schema + query     │
       │          │  + error type       │
       │          │  + skill content    │
       │          │  + past fixes       │
       │          └──────────┬──────────┘
       │                     │
       │                     ▼
       │          ┌─────────────────────┐
       │          │   Anthropic API     │
       │          └──────────┬──────────┘
       │                     │
       │                     ▼
       │          ┌─────────────────────┐
       │          │  parse response     │
       │          │  <fixed_query>      │
       │          │  <fix_explanation>  │
       │          │  <skill_body>       │
       │          └──────────┬──────────┘
       │                     │
       │              max iterations?
       │              ┌──────┴──────┐
       │             yes            no
       │              │             │
       │              ▼             └──────────────┐
       │         return best                       │
       │         attempt ✗                         │
       │                                           ▼
       │                               back to execute() ↑
       │
       ▼
  ┌──────────────────────┐
  │ skill body returned? │
  └──────┬───────────────┘
         │
    ┌────┴────┐
   yes        no
    │          │
    ▼          ▼
  save      return
  skill      result ✓
  .md
    │
    ▼
  return
  result ✓
```

---

## Learning Across Runs

```
  RUN 1 — no prior knowledge
  ───────────────────────────────────────────────────────────────

  broken query
      │
      ▼
  execute ──► FAIL "no such column: pric"
      │
      ▼
  load_skill("no_such_column")  ──► None  (no skill yet)
      │
      ▼
  get_similar_failures()  ──► []  (nothing in memory)
      │
      ▼
  Claude prompt: schema + error only
      │
      ▼
  Claude: fixed_query + skill_body
      │
      ├──► execute fixed query ──► SUCCESS
      │
      ├──► memory.json  { failure + fix recorded }
      │
      └──► skills/no_such_column.md  { skill created }


  RUN 2 — skill + past example available
  ───────────────────────────────────────────────────────────────

  same broken query
      │
      ▼
  execute ──► FAIL "no such column: pric"
      │
      ▼
  load_skill("no_such_column")  ──► strategy + example from .md
      │
      ▼
  get_similar_failures()  ──► [ { original, fixed, explanation } ]
      │
      ▼
  Claude prompt: schema + error + skill + past fix
      │
      ▼
  Claude: fixed_query  (richer context → fewer iterations)
      │
      ├──► execute fixed query ──► SUCCESS
      │
      ├──► memory.json  { updated }
      │
      └──► skills/no_such_column.md  { success_rate updated }
```

---

## File Structure

```
self-learning-agent/
├── run_demo.py              entry point, 5 broken demo queries
├── config.py                paths, model name, MAX_ITERATIONS
├── plan.md                  design document
├── architecture.md          this file
├── requirements.txt
│
├── agent/
│   ├── core.py              SQLLearningAgent — main loop
│   ├── memory.py            MemoryStore — JSON read/write
│   ├── skill_manager.py     SkillManager — Markdown files
│   ├── sql_executor.py      SQLExecutor — runs SQLite queries
│   └── classifier.py        ErrorClassifier — error → type
│
├── skills/                  auto-generated skill files
│   ├── syntax_error.md
│   ├── no_such_column.md
│   ├── no_such_table.md
│   └── ambiguous_column.md
│
└── data/
    ├── sample.db            SQLite e-commerce database
    └── memory.json          failure log + error pattern counts
```
