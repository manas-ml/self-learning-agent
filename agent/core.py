from __future__ import annotations

import re

import anthropic

import config
from agent.classifier import ErrorClassifier
from agent.memory import MemoryStore
from agent.skill_manager import SkillManager
from agent.sql_executor import SQLExecutor


_SYSTEM = """\
You are a SQL query repair agent. Your job is to fix a broken SQL query by diagnosing the error \
and producing a corrected version.

You are given:
- The original (broken) SQL query
- The SQLite error message
- The database schema
- (Optional) A relevant skill file describing known fixes for this error type
- (Optional) Examples of similar past failures that were successfully fixed

Respond using EXACTLY these XML tags:

<fixed_query>
The corrected SQL query here (SQL only, no markdown fences)
</fixed_query>

<fix_explanation>
One or two sentences explaining what was wrong and what you changed.
</fix_explanation>

<skill_body>
A concise Markdown guide (2–4 paragraphs + one before/after example) that teaches how to fix this \
class of error. This will be stored as a reusable skill. Include a ## Strategy section, \
a ## Common Patterns section, and a ## Example section. Leave empty if a skill already exists \
and no new insight was gained.
</skill_body>
"""


def _extract(tag: str, text: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


class SQLLearningAgent:
    def __init__(self):
        self.executor = SQLExecutor(config.SAMPLE_DB_PATH)
        self.memory = MemoryStore(config.MEMORY_PATH)
        self.skills = SkillManager(config.SKILLS_DIR)
        self.classifier = ErrorClassifier()
        self._client = anthropic.Anthropic()
        self._schema: str | None = None

    def _get_schema(self) -> str:
        if self._schema is None:
            self._schema = self.executor.get_schema()
        return self._schema

    def _call_claude(self, user_message: str) -> str:
        response = self._client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def _build_prompt(
        self,
        original_query: str,
        current_query: str,
        error_message: str,
        error_type: str,
        skill: dict | None,
        similar: list[dict],
    ) -> str:
        parts = [
            f"## Database Schema\n{self._get_schema()}",
            f"## Original Query\n```sql\n{original_query}\n```",
        ]
        if current_query != original_query:
            parts.append(f"## Last Attempted Query\n```sql\n{current_query}\n```")
        parts.append(f"## Error\n**Type:** {error_type}\n**Message:** {error_message}")

        if skill:
            parts.append(f"## Relevant Skill\n{skill['body']}")

        if similar:
            examples = []
            for s in similar:
                examples.append(
                    f"- **Broken:** `{s['original_query']}`\n"
                    f"  **Fixed:** `{s['fixed_query']}`\n"
                    f"  **Why:** {s['fix_description']}"
                )
            parts.append("## Similar Past Fixes\n" + "\n".join(examples))

        return "\n\n".join(parts)

    def improve(self, original_query: str) -> dict:
        current_query = original_query
        failure_id: int | None = None
        error_types_seen: list[str] = []
        skill_name: str | None = None
        last_explanation = ""
        last_skill_body = ""

        for iteration in range(1, config.MAX_ITERATIONS + 1):
            rows, error = self.executor.execute(current_query)

            if error is None:
                if failure_id is not None:
                    self.memory.record_success(
                        failure_id,
                        fixed_query=current_query,
                        fix_description=last_explanation,
                        iterations=iteration - 1,
                        skill_generated=skill_name,
                    )
                if last_skill_body:
                    error_type = error_types_seen[-1] if error_types_seen else "unknown_error"
                    existing = self.skills.load_skill(error_type)
                    description = f"Fix {error_type.replace('_', ' ')} errors in SQL"
                    self.skills.save_skill(
                        error_type,
                        description,
                        last_skill_body,
                        existing_meta=existing["meta"] if existing else None,
                    )
                    skill_name = error_type
                    self.skills.update_success_rate(error_type, was_success=True)

                return {
                    "original_query": original_query,
                    "final_query": current_query,
                    "success": True,
                    "iterations": iteration - 1,
                    "rows_returned": len(rows),
                    "error_types_seen": error_types_seen,
                    "skill_created_or_updated": skill_name,
                }

            error_type = self.classifier.classify(error)
            error_types_seen.append(error_type)

            if failure_id is None:
                failure_id = self.memory.record_failure(original_query, error_type, error)

            skill = self.skills.load_skill(error_type)
            similar = self.memory.get_similar_failures(error_type)

            prompt = self._build_prompt(
                original_query, current_query, error, error_type, skill, similar
            )
            response = self._call_claude(prompt)

            fixed_query = _extract("fixed_query", response)
            last_explanation = _extract("fix_explanation", response)
            last_skill_body = _extract("skill_body", response)

            if not fixed_query:
                break

            if skill:
                self.skills.update_success_rate(error_type, was_success=False)

            current_query = fixed_query

        # exhausted iterations without success
        if failure_id is not None:
            self.memory.record_success(
                failure_id,
                fixed_query=current_query,
                fix_description=last_explanation or "Max iterations reached without full success.",
                iterations=config.MAX_ITERATIONS,
                skill_generated=None,
            )

        return {
            "original_query": original_query,
            "final_query": current_query,
            "success": False,
            "iterations": config.MAX_ITERATIONS,
            "rows_returned": 0,
            "error_types_seen": error_types_seen,
            "skill_created_or_updated": None,
        }
