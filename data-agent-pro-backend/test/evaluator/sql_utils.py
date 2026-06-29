import re
from decimal import Decimal
from typing import Any


_SQL_FENCE_PATTERN = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def extract_sql(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    fenced = _SQL_FENCE_PATTERN.search(stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    stripped = stripped.strip("` \n\t;")
    return stripped or None


def normalize_sql(sql: str | None) -> str:
    if not sql:
        return ""
    return re.sub(r"\s+", " ", sql).strip().lower()


def contains_all(sql: str | None, expected_items: list[str]) -> bool:
    if not expected_items:
        return True
    normalized = normalize_sql(sql)
    return all(item.lower() in normalized for item in expected_items)


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return round(float(value), 6)
    if isinstance(value, float):
        return round(value, 6)
    return value


def values_close(left: Any, right: Any, tolerance: float = 0.01) -> bool:
    left_value = normalize_value(left)
    right_value = normalize_value(right)
    if isinstance(left_value, int | float) and isinstance(right_value, int | float):
        return abs(float(left_value) - float(right_value)) <= tolerance
    return str(left_value) == str(right_value)


def normalize_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if rows is None:
        return []

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized_row = {str(key).lower(): normalize_value(value) for key, value in row.items()}
        normalized_rows.append(normalized_row)

    return sorted(normalized_rows, key=lambda item: repr(sorted(item.items())))


def rows_equal(left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None) -> bool:
    return normalize_rows(left) == normalize_rows(right)


def row_values_match(left: dict[str, Any], right: dict[str, Any], tolerance: float = 0.01) -> bool:
    left_values = list(left.values())
    right_values = list(right.values())
    if len(left_values) != len(right_values):
        return False

    used_indexes: set[int] = set()
    for left_value in left_values:
        matched_index = None
        for index, right_value in enumerate(right_values):
            if index in used_indexes:
                continue
            if values_close(left_value, right_value, tolerance):
                matched_index = index
                break
        if matched_index is None:
            return False
        used_indexes.add(matched_index)
    return True


def rows_semantically_equal(left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None, tolerance: float = 0.01) -> bool:
    if left is None or right is None or len(left) != len(right):
        return False

    used_indexes: set[int] = set()
    for left_row in left:
        matched_index = None
        for index, right_row in enumerate(right):
            if index in used_indexes:
                continue
            if row_values_match(left_row, right_row, tolerance):
                matched_index = index
                break
        if matched_index is None:
            return False
        used_indexes.add(matched_index)
    return True


def result_set_f1(left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None, tolerance: float = 0.01) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0

    matched_right: set[int] = set()
    matches = 0
    for left_row in left:
        for index, right_row in enumerate(right):
            if index in matched_right:
                continue
            if row_values_match(left_row, right_row, tolerance):
                matched_right.add(index)
                matches += 1
                break

    precision = matches / len(right)
    recall = matches / len(left)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def sql_exact_match(left: str | None, right: str | None) -> bool:
    return normalize_sql(left).rstrip(";") == normalize_sql(right).rstrip(";")


def aggregation_match(sql: str | None, gold_sql: str | None) -> bool:
    generated = normalize_sql(sql)
    gold = normalize_sql(gold_sql)
    aggregation_keywords = ["sum(", "count(", "avg(", "min(", "max(", "group by", "order by", "limit"]
    required = [keyword for keyword in aggregation_keywords if keyword in gold]
    return all(keyword in generated for keyword in required)