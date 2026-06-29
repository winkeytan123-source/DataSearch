from dataclasses import dataclass

import sqlglot
from sqlglot import expressions as exp


PROHIBITED_STATEMENTS = {
    "Insert",
    "Update",
    "Delete",
    "Drop",
    "Alter",
    "Truncate",
    "TruncateTable",
    "Create",
    "Command",
}

DANGEROUS_KEYWORDS = {
    "information_schema",
    "mysql.user",
    "sys.",
    "performance_schema",
    "load_file",
    "outfile",
    "dumpfile",
    "sleep",
    "benchmark",
}


@dataclass
class SQLSecurityResult:
    valid: bool
    error: str | None = None


def validate_select_sql_security(sql: str, table_infos: list[dict]) -> SQLSecurityResult:
    try:
        expressions = sqlglot.parse(sql, read="mysql")
    except Exception as exc:
        return SQLSecurityResult(False, f"SQL 解析失败：{exc}")

    if len(expressions) != 1:
        return SQLSecurityResult(False, "禁止多语句执行，只允许单条 SELECT")

    expression = expressions[0]

    prohibited = find_prohibited_statement(expression)
    if prohibited:
        return SQLSecurityResult(False, f"禁止执行 {prohibited} 语句")

    if not isinstance(expression, exp.Select):
        return SQLSecurityResult(False, "只允许单条 SELECT 查询")

    if any(isinstance(node, exp.Star) for node in expression.walk()):
        return SQLSecurityResult(False, "禁止 SELECT *")

    malicious_error = detect_malicious_sql(sql, expression)
    if malicious_error:
        return SQLSecurityResult(False, malicious_error)

    auth_error = validate_authorized_objects(expression, table_infos)
    if auth_error:
        return SQLSecurityResult(False, auth_error)

    return SQLSecurityResult(True)


def find_prohibited_statement(expression: exp.Expression) -> str | None:
    # 先检查根表达式本身
    node_name = expression.__class__.__name__
    if node_name in PROHIBITED_STATEMENTS:
        return node_name.upper()
    # 遍历子表达式（sqlglot walk() 可能返回 tuple 或 node）
    for node in expression.walk():
        expr_node = node[0] if isinstance(node, tuple) else node
        node_name = expr_node.__class__.__name__
        if node_name in PROHIBITED_STATEMENTS:
            return node_name.upper()
    return None


def detect_malicious_sql(sql: str, expression: exp.Expression) -> str | None:
    normalized_sql = sql.lower()
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in normalized_sql:
            return f"疑似恶意 SQL：包含危险关键字 {keyword}"

    for func in expression.find_all(exp.Func):
        func_name = func.sql_name().lower()
        if func_name in {"load_file", "sleep", "benchmark"}:
            return f"疑似恶意 SQL：禁止调用函数 {func_name}"
    return None


def validate_authorized_objects(expression: exp.Expression, table_infos: list[dict]) -> str | None:
    allowed_tables, allowed_columns = build_allowed_objects(table_infos)
    if not allowed_tables:
        return "未找到可授权访问的表信息"

    table_aliases: dict[str, str] = {}
    used_tables: set[str] = set()
    for table in expression.find_all(exp.Table):
        table_name = normalize_identifier(table.name)
        if table.db or table.catalog:
            return f"禁止访问指定库名的表：{table.sql()}"
        if table_name not in allowed_tables:
            return f"禁止访问未授权表：{table_name}"
        used_tables.add(table_name)
        table_aliases[normalize_identifier(table.alias_or_name)] = table_name

    if not used_tables:
        return "SELECT 必须显式指定 FROM 表"

    for column in expression.find_all(exp.Column):
        column_name = normalize_identifier(column.name)
        table_name = normalize_identifier(column.table) if column.table else None

        if table_name:
            resolved_table = table_aliases.get(table_name, table_name)
            if resolved_table not in allowed_tables:
                return f"禁止访问未授权表或别名：{table_name}"
            if column_name not in allowed_columns.get(resolved_table, set()):
                return f"禁止访问未授权字段：{resolved_table}.{column_name}"
            continue

        matched_tables = [table for table in used_tables if column_name in allowed_columns.get(table, set())]
        if not matched_tables:
            return f"禁止访问未授权字段：{column_name}"

    return None


def build_allowed_objects(table_infos: list[dict]) -> tuple[set[str], dict[str, set[str]]]:
    allowed_tables: set[str] = set()
    allowed_columns: dict[str, set[str]] = {}
    for table in table_infos:
        table_name = normalize_identifier(table.get("name"))
        if not table_name:
            continue
        allowed_tables.add(table_name)
        allowed_columns[table_name] = {
            normalize_identifier(column.get("name"))
            for column in table.get("columns", [])
            if normalize_identifier(column.get("name"))
        }
    return allowed_tables, allowed_columns


def normalize_identifier(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip("` ").lower()