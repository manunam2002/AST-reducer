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
