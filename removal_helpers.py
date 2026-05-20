import sqlglot
from sqlglot import exp

def statements_to_sql(statements) -> str:
    return ";\n".join(
        stmt.sql(dialect="sqlite")
        for stmt in statements
        if stmt is not None
    ) + ";"


def remove_sql_statement(statements):
    if len(statements) <= 1:
        return

    for i in range(len(statements)):
        candidate_statements = statements[:i] + statements[i + 1:]

        if not candidate_statements:
            continue

        yield statements_to_sql(candidate_statements)


def remove_insert_rows(statements):
    for stmt_index, stmt in enumerate(statements):
        if not isinstance(stmt, exp.Insert):
            continue

        values = stmt.find(exp.Values)
        if values is None:
            continue

        rows = values.expressions

        if len(rows) <= 1:
            continue

        for row_index in range(len(rows)):
            candidate_stmt = stmt.copy()
            candidate_values = candidate_stmt.find(exp.Values)

            new_rows = (
                candidate_values.expressions[:row_index]
                + candidate_values.expressions[row_index + 1:]
            )

            candidate_values.set("expressions", new_rows)

            candidate_statements = statements.copy()
            candidate_statements[stmt_index] = candidate_stmt

            yield statements_to_sql(candidate_statements)

def reduce_clause_items(statements):
    for stmt_index, stmt in enumerate(statements):

        # WHERE / HAVING: replace one predicate/expression with TRUE
        for clause_type in [exp.Where, exp.Having]:
            clause = stmt.find(clause_type)

            if clause is None:
                continue

            expressions = list(clause.find_all(exp.Expression))

            for expr_index, _ in enumerate(expressions):
                candidate_stmt = stmt.copy()
                candidate_clause = candidate_stmt.find(clause_type)

                candidate_expressions = list(
                    candidate_clause.find_all(exp.Expression)
                )

                if expr_index >= len(candidate_expressions):
                    continue

                candidate_expressions[expr_index].replace(exp.true())

                candidate_statements = statements.copy()
                candidate_statements[stmt_index] = candidate_stmt

                yield statements_to_sql(candidate_statements)

        # ORDER BY: remove one ordering expression
        order = stmt.find(exp.Order)

        if order is not None:
            order_items = order.expressions

            for item_index in range(len(order_items)):
                candidate_stmt = stmt.copy()
                candidate_order = candidate_stmt.find(exp.Order)

                new_items = (
                    candidate_order.expressions[:item_index]
                    + candidate_order.expressions[item_index + 1:]
                )

                if not new_items:
                    continue

                candidate_order.set("expressions", new_items)

                candidate_statements = statements.copy()
                candidate_statements[stmt_index] = candidate_stmt

                yield statements_to_sql(candidate_statements)

        # GROUP BY: remove one grouped expression
        group = stmt.find(exp.Group)

        if group is not None:
            group_items = group.expressions

            for item_index in range(len(group_items)):
                candidate_stmt = stmt.copy()
                candidate_group = candidate_stmt.find(exp.Group)

                new_items = (
                    candidate_group.expressions[:item_index]
                    + candidate_group.expressions[item_index + 1:]
                )

                if not new_items:
                    continue

                candidate_group.set("expressions", new_items)

                candidate_statements = statements.copy()
                candidate_statements[stmt_index] = candidate_stmt

                yield statements_to_sql(candidate_statements)