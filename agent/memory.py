from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class MemoryStore:
    def __init__(self, json_path: Path):
        self._path = json_path
        json_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return {"failures": [], "error_patterns": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def record_failure(self, original_query: str, error_type: str, error_message: str) -> int:
        entry = {
            "id": len(self._data["failures"]),
            "original_query": original_query,
            "error_type": error_type,
            "error_message": error_message,
            "fixed_query": None,
            "fix_description": None,
            "iterations": 1,
            "success": False,
            "skill_generated": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._data["failures"].append(entry)

        pattern = self._data["error_patterns"].setdefault(
            error_type, {"occurrences": 0, "last_seen": None}
        )
        pattern["occurrences"] += 1
        pattern["last_seen"] = entry["timestamp"]

        self._save()
        return entry["id"]

    def record_success(
        self,
        failure_id: int,
        fixed_query: str,
        fix_description: str,
        iterations: int,
        skill_generated: str | None,
    ) -> None:
        for entry in self._data["failures"]:
            if entry["id"] == failure_id:
                entry.update(
                    fixed_query=fixed_query,
                    fix_description=fix_description,
                    iterations=iterations,
                    success=True,
                    skill_generated=skill_generated,
                )
                break
        self._save()

    def get_similar_failures(self, error_type: str, limit: int = 3) -> list[dict]:
        matches = [
            {
                "original_query": e["original_query"],
                "fixed_query": e["fixed_query"],
                "fix_description": e["fix_description"],
            }
            for e in self._data["failures"]
            if e["error_type"] == error_type and e["success"]
        ]
        return matches[-limit:]

    def get_error_stats(self) -> list[dict]:
        return [
            {"error_type": k, "occurrences": v["occurrences"], "last_seen": v["last_seen"]}
            for k, v in sorted(
                self._data["error_patterns"].items(),
                key=lambda x: x[1]["occurrences"],
                reverse=True,
            )
        ]
