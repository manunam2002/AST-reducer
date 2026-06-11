import sqlglot
from sqlglot import exp

from removal_helpers import statements_to_sql

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
