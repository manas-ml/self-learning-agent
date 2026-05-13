import re


class ErrorClassifier:
    _PATTERNS = [
        (r"syntax error", "syntax_error"),
        (r"no such table", "no_such_table"),
        (r"no such column", "no_such_column"),
        (r"datatype mismatch", "type_mismatch"),
        (r"ambiguous column", "ambiguous_column"),
        (r"UNIQUE constraint failed", "constraint_violation"),
        (r"table .+ already exists", "table_exists"),
        (r"not null constraint", "not_null_violation"),
    ]

    def classify(self, error_message: str) -> str:
        lower = error_message.lower()
        for pattern, error_type in self._PATTERNS:
            if re.search(pattern, lower):
                return error_type
        return "unknown_error"
