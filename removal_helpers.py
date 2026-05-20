import sqlglot


def remove_sql_statement(sql: str):
    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except Exception:
        return

    # sqlglot can return None for unparsable/empty statements
    statements = [stmt for stmt in statements if stmt is not None]

    if len(statements) <= 1:
        return

    for i in range(len(statements)):
        candidate_statements = statements[:i] + statements[i + 1:]

        if not candidate_statements:
            continue

        candidate_sql = ";\n".join(
            stmt.sql(dialect="sqlite")
            for stmt in candidate_statements
            if stmt is not None
        ) + ";"

        yield candidate_sql