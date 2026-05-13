from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml


class SkillManager:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, error_type: str) -> Path:
        return self.skills_dir / f"{error_type}.md"

    def _parse(self, content: str) -> tuple[dict, str]:
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return meta, body
        return {}, content.strip()

    def load_skill(self, error_type: str) -> dict | None:
        path = self._path(error_type)
        if not path.exists():
            return None
        meta, body = self._parse(path.read_text())
        return {"meta": meta, "body": body}

    def save_skill(
        self,
        error_type: str,
        description: str,
        body: str,
        existing_meta: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if existing_meta:
            meta = dict(existing_meta)
            meta["last_updated"] = now
            meta["usage_count"] = meta.get("usage_count", 0) + 1
            meta["description"] = description
        else:
            meta = {
                "name": error_type,
                "description": description,
                "error_types": [error_type],
                "success_rate": 0.0,
                "usage_count": 1,
                "created_at": now,
                "last_updated": now,
            }
        frontmatter = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
        self._path(error_type).write_text(f"---\n{frontmatter}---\n\n{body}\n")

    def update_success_rate(self, error_type: str, was_success: bool) -> None:
        skill = self.load_skill(error_type)
        if not skill:
            return
        meta = skill["meta"]
        count = meta.get("usage_count", 1)
        current = meta.get("success_rate", 0.0)
        # running average
        meta["success_rate"] = round((current * (count - 1) + (1.0 if was_success else 0.0)) / count, 3)
        frontmatter = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
        self._path(error_type).write_text(f"---\n{frontmatter}---\n\n{skill['body']}\n")

    def list_skills(self) -> list[dict]:
        skills = []
        for path in sorted(self.skills_dir.glob("*.md")):
            meta, _ = self._parse(path.read_text())
            skills.append(meta)
        return skills
