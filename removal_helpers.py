from platform import node
import sqlglot
from sqlglot import exp

def statements_to_sql(statements) -> str:
    parts = []
    for s in statements:
        if isinstance(s, exp.Command):
            raw = f"{s.this} {s.expression}".strip()
            if raw:
                parts.append(raw)
        else:
            try:
                sql = s.sql(dialect='sqlite', pretty=False).strip()
                if sql:
                    parts.append(sql)
            except Exception:
                pass  # skip statements that can't be serialized
    return ";\n".join(parts)


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




def get_stmt_targets(statements):
    return list(range(len(statements)))

def remove_stmt(statements, target_idx):
    candidate = statements[:target_idx] + statements[target_idx + 1:]
    if not candidate:
        # Never reduce to zero statements
        return statements_to_sql(statements)
    return statements_to_sql(candidate)


def get_insert_row_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if not isinstance(stmt, exp.Insert):
            continue
        values = stmt.args.get("expression")
        if not isinstance(values, exp.Values):
            continue
        rows = values.expressions
        if len(rows) > 1:
            for r_idx in range(len(rows)):
                targets.append((s_idx, r_idx))
    return targets

def remove_insert_row(statements, target):
    s_idx, r_idx = target
    candidate_stmts = [s.copy() for s in statements]
    values = candidate_stmts[s_idx].args.get("expression")
    rows = list(values.expressions)
    if r_idx < len(rows) and len(rows) > 1:
        values.set("expressions", [r for i, r in enumerate(rows) if i != r_idx])
    return statements_to_sql(candidate_stmts)


def get_insert_modifier_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Insert) and stmt.args.get("overwrite") or stmt.args.get("alternative"):
            targets.append(s_idx)
    return targets

def remove_insert_modifier(statements, target):
    s_idx = target
    candidate_stmts = [s.copy() for s in statements]
    candidate_stmts[s_idx].set("alternative", None)
    return statements_to_sql(candidate_stmts)


def get_clause_targets(statements):
    targets = []
    clause_types = (exp.Join, exp.Where, exp.Order, exp.Group, exp.Having, exp.Limit)

    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        for c_type in clause_types:
            count = len(list(stmt.find_all(c_type)))
            for n_idx in range(count):
                targets.append((s_idx, c_type, n_idx))
    return targets

def remove_clause(statements, target):
    s_idx, c_type, n_idx = target
    candidate_stmts = [s.copy() for s in statements]

    nodes = list(candidate_stmts[s_idx].find_all(c_type))
    if n_idx < len(nodes):
        nodes[n_idx].pop()

    return statements_to_sql(candidate_stmts)


def get_select_expr_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        selects = list(stmt.find_all(exp.Select))
        for sel_idx, select_node in enumerate(selects):
            count = len(select_node.expressions)
            if count > 1:
                for e_idx in range(count):
                    targets.append((s_idx, sel_idx, e_idx))
    return targets

def remove_select_expr(statements, target):
    s_idx, sel_idx, e_idx = target
    candidate_stmts = [s.copy() for s in statements]
    selects = list(candidate_stmts[s_idx].find_all(exp.Select))
    if sel_idx < len(selects):
        select_node = selects[sel_idx]
        exprs = list(select_node.expressions)
        if e_idx < len(exprs) and len(exprs) > 1:
            select_node.set("expressions", [e for i, e in enumerate(exprs) if i != e_idx])
    return statements_to_sql(candidate_stmts)


def get_in_list_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        in_nodes = list(stmt.find_all(exp.In))
        for in_idx, in_node in enumerate(in_nodes):
            # exp.In can be either an IN (...) list or an IN (subquery)
            # only target list form, not subqueries
            exprs = in_node.args.get("expressions", [])
            if len(exprs) > 1:
                for e_idx in range(len(exprs)):
                    targets.append((s_idx, in_idx, e_idx))
    return targets

def remove_in_item(statements, target):
    s_idx, in_idx, e_idx = target
    candidate_stmts = [s.copy() for s in statements]
    in_nodes = list(candidate_stmts[s_idx].find_all(exp.In))
    if in_idx < len(in_nodes):
        in_node = in_nodes[in_idx]
        exprs = in_node.args.get("expressions", [])
        if e_idx < len(exprs) and len(exprs) > 1:
            in_node.set("expressions", [e for i, e in enumerate(exprs) if i != e_idx])
    return statements_to_sql(candidate_stmts)


def get_binary_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        binaries = list(stmt.find_all((exp.And, exp.Or)))
        for b_idx in range(len(binaries)):
            targets.append((s_idx, b_idx, 0)) # Try Left side
            targets.append((s_idx, b_idx, 1)) # Try Right side
    return targets

def remove_binary(statements, target):
    s_idx, b_idx, side = target
    candidate_stmts = [s.copy() for s in statements]
    binaries = list(candidate_stmts[s_idx].find_all((exp.And, exp.Or)))
    
    if b_idx < len(binaries):
        node = binaries[b_idx]
        replacement = node.left if side == 0 else node.right
        node.replace(replacement)
        
    return statements_to_sql(candidate_stmts)


def get_unnest_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        subqueries = list(stmt.find_all(exp.Subquery))
        for sq_idx in range(len(subqueries)):
            targets.append((s_idx, sq_idx))
    return targets

def remove_unnest(statements, target):
    s_idx, sq_idx = target
    candidate_stmts = [s.copy() for s in statements]
    subqueries = list(candidate_stmts[s_idx].find_all(exp.Subquery))
    
    if sq_idx < len(subqueries):
        node = subqueries[sq_idx]
        inner = node.this
        if node.alias:
            inner.set("alias", node.args.get("alias"))
        node.replace(inner)
        
    return statements_to_sql(candidate_stmts)


REQUIRES_THIS = (exp.Cast, exp.TryCast, exp.Extract, exp.Dot, exp.Alias, exp.Bracket, exp.Anonymous, exp.Paren)
REQUIRES_MULTI_ARGS = (exp.Nullif, exp.Coalesce, exp.Greatest, exp.Least)

def iter_ancestors(node):
    current = node.parent
    while current is not None:
        yield current
        current = current.parent

def safe_replace(node, replacement):
    parent = node.parent
    if isinstance(parent, REQUIRES_THIS) and parent.args.get("this") is node:
        parent.replace(replacement)
        return
    if isinstance(parent, REQUIRES_MULTI_ARGS):
        parent.replace(replacement)
        return
    for ancestor in iter_ancestors(node):
        if isinstance(ancestor, exp.When):
            case_node = ancestor.parent
            if isinstance(case_node, exp.Case):
                whens = case_node.args.get("ifs", [])
                if len(whens) > 1:
                    case_node.set("ifs", [w for w in whens if w is not ancestor])
                else:
                    case_node.replace(case_node.args.get("default") or exp.Null())
            else:
                ancestor.replace(replacement)
            return
    node.replace(replacement)

def safe_pop(node):
    parent = node.parent
    if isinstance(parent, REQUIRES_THIS) and parent.args.get("this") is node:
        parent.replace(exp.Null())
        return
    if isinstance(parent, REQUIRES_MULTI_ARGS):
        parent.replace(exp.Null())
        return
    for ancestor in iter_ancestors(node):
        if isinstance(ancestor, exp.When):
            case_node = ancestor.parent
            if isinstance(case_node, exp.Case):
                whens = case_node.args.get("ifs", [])
                if len(whens) > 1:
                    case_node.set("ifs", [w for w in whens if w is not ancestor])
                else:
                    case_node.replace(case_node.args.get("default") or exp.Null())
            else:
                ancestor.replace(exp.Null())
            return
    node.pop()

def get_leaf_targets(statements):
    targets = []
    leaf_types = (exp.Column, exp.Literal, exp.ColumnDef, exp.Case)
    
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        for l_type in leaf_types:
            count = len(list(stmt.find_all(l_type)))
            for n_idx in range(count):
                targets.append((s_idx, l_type, n_idx))
    return targets

def remove_leaf(statements, target):
    s_idx, l_type, n_idx = target
    candidate_stmts = [s.copy() for s in statements]
    nodes = list(candidate_stmts[s_idx].find_all(l_type))
    if n_idx >= len(nodes):
        return statements_to_sql(candidate_stmts)
    node = nodes[n_idx]

    if isinstance(node, exp.ColumnDef):
        node.pop()
    elif isinstance(node, exp.Case):
        safe_replace(node, node.args.get('default') or exp.Null())
    elif isinstance(node, exp.Literal):
        if node.is_string:
            if node.this == "":
                return statements_to_sql(candidate_stmts)
            node.replace(exp.Literal.string(""))
        else:
            val = float(node.this)
            if val == 0:
                return statements_to_sql(candidate_stmts)
            node.replace(exp.Literal.number(1))
    else:
        safe_pop(node)

    return statements_to_sql(candidate_stmts)


def get_constantizer_targets(statements):
    targets = []
    types = (exp.Case, exp.Binary, exp.Nullif, exp.Coalesce, exp.Window)
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        nodes = list(stmt.find_all(types))
        for n_idx in range(len(nodes)):
            targets.append((s_idx, n_idx, "null"))
            targets.append((s_idx, n_idx, "one"))
    return targets

def remove_constantizer(statements, target):
    s_idx, n_idx, replacement_tag = target
    candidate_stmts = [s.copy() for s in statements]
    types = (exp.Case, exp.Binary, exp.Nullif, exp.Coalesce, exp.Window)
    nodes = list(candidate_stmts[s_idx].find_all(types))
    if n_idx < len(nodes):
        replacement = exp.Null() if replacement_tag == "null" else exp.Literal.number(1)
        safe_replace(nodes[n_idx], replacement)
    return statements_to_sql(candidate_stmts)


def get_cte_targets(statements):
    targets = []
    for s_idx, stmt in enumerate(statements):
        if isinstance(stmt, exp.Command):
            continue
        ctes = stmt.args.get("with")
        if not ctes:
            continue
        for c_idx, cte in enumerate(ctes.expressions):
            targets.append((s_idx, c_idx))
    return targets

def remove_cte(statements, target):
    s_idx, c_idx = target
    candidate_stmts = [s.copy() for s in statements]
    ctes = candidate_stmts[s_idx].args.get("with")
    if ctes:
        expressions = list(ctes.expressions)
        if c_idx < len(expressions):
            expressions.pop(c_idx)
            if expressions:
                ctes.set("expressions", expressions)
            else:
                candidate_stmts[s_idx].set("with", None)
    return statements_to_sql(candidate_stmts)


def remove_multiple(statements, targets, remove_fn):
    candidate_stmts = [s.copy() for s in statements]
    for target in reversed(targets):
        sql = remove_fn(candidate_stmts, target)
        try:
            new_stmts = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
            candidate_stmts = new_stmts
        except Exception as e:
            print(f"Error occurred: {e}")
            # This chunk produces invalid SQL at some intermediate step, abort
            return statements_to_sql(statements)
    return statements_to_sql(candidate_stmts)


def linear_reduce(statements, get_targets, oracle, remove, reduce_once):
    changed_in_this_pass = False
    targets = get_targets(statements)
    original_sql = statements_to_sql(statements)

    for target in reversed(targets):
        candidate_sql = remove(statements, target)
        if candidate_sql == original_sql:
            continue
        if oracle(candidate_sql):
            try:
                new_statements = [s for s in sqlglot.parse(candidate_sql, read="sqlite") if s is not None]
                changed_in_this_pass = True
                statements[:] = new_statements
                original_sql = statements_to_sql(statements)
            except Exception as e:
                print(f"Error occurred while parsing reduced SQL: {e}")
            if reduce_once:
                break
    return changed_in_this_pass


def ddmin_reduce(statements, get_targets, oracle, remove):
    targets = get_targets(statements)
    if not targets:
        return False

    n = 2
    changed = False
    seen = set()

    while len(targets) >= 1:
        chunk_size = max(1, len(targets) // n)
        chunks = [targets[i:i+chunk_size] for i in range(0, len(targets), chunk_size)]
        
        reduced = False
        for chunk in chunks:
            chunk_key = tuple(sorted(str(t) for t in chunk))
            if chunk_key in seen:
                continue
            seen.add(chunk_key)

            candidate_sql = remove_multiple(statements, chunk, remove)
            if candidate_sql == statements_to_sql(statements):
                continue
            if oracle(candidate_sql):
                try:
                    statements[:] = [s for s in sqlglot.parse(candidate_sql, read="sqlite") if s is not None]
                except Exception as e:
                    print(f"Error occurred while parsing reduced SQL: {e}")
                    continue
                targets = get_targets(statements)
                seen.clear()
                n = max(2, n - 1)
                reduced = True
                changed = True
                break
        
        if not reduced:
            if n >= len(targets):
                break
            n = min(n * 2, len(targets))

    return changed
