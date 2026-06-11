import sqlglot
from sqlglot import exp

from utils import read_file, write_file
from oracle import bug_still_exists
from removal_helpers import *
from reduction_passes import *

oracle_cache = {}

def cached_bug_still_exists(candidate_sql: str, oracle_path: str) -> bool:
    key = candidate_sql.strip()
    
    if not key:
        return False
    
    if key in oracle_cache:
        return oracle_cache[key]

    result = bug_still_exists(candidate_sql, oracle_path)
    oracle_cache[key] = result
    return result

def parse_sql(sql: str):
    statements = sqlglot.parse(sql, read="sqlite", error_level=sqlglot.ErrorLevel.IGNORE)
    result = []
    for s in statements:
        if s is None:
            continue
        # Filter malformed Updates (table name got lost)
        if isinstance(s, exp.Update) and s.args.get("this") is None:
            continue
        rendered = s.sql(dialect='sqlite').strip()
        if not rendered:
            continue
        result.append(s)
    return result

# Main reduction loop
def reduce_query(query_path: str, oracle_path: str) -> None:
    sql = read_file(query_path)
    print("Original SQL:")
    print(sql)

    statements = parse_sql(sql)

    passes = [
        (get_stmt_targets,         remove_stmt,         "linear_once"),
        (get_insert_row_targets,   remove_insert_row,   "ddmin"),
        (get_insert_modifier_targets, remove_insert_modifier, "linear_once"),
        (get_clause_targets,       remove_clause,       "linear_once"),
        (get_cte_targets,          remove_cte,          "linear_once"),
        (get_select_expr_targets,  remove_select_expr,  "ddmin"),
        (get_in_list_targets,      remove_in_item,      "ddmin"),
        (get_binary_targets,       remove_binary,       "linear"),
        (get_unnest_targets,       remove_unnest,       "linear_once"),
        (get_leaf_targets,         remove_leaf,         "linear"),
        (get_constantizer_targets, remove_constantizer, "linear"),
    ]

    oracle = lambda sql: cached_bug_still_exists(sql, oracle_path)
    changed = True

    while changed:
        changed = False
        for get_targets, remove, strategy in passes:
            print(f"Applying pass: {get_targets.__name__} + {remove.__name__}")
            if strategy == "linear":
                if linear_reduce(statements, get_targets, oracle, remove, False):
                    print(f"Current SQL:\n{statements_to_sql(statements)}")
                    changed = True
                    break
            elif strategy == "linear_once":
                if linear_reduce(statements, get_targets, oracle, remove, True):
                    print(f"Current SQL:\n{statements_to_sql(statements)}")
                    changed = True
                    break
            elif strategy == "ddmin":
                if ddmin_reduce(statements, get_targets, oracle, remove):
                    print(f"Current SQL:\n{statements_to_sql(statements)}")
                    changed = True
                    break

    final_sql = statements_to_sql(statements)
    print("Final reduced SQL:")
    print(final_sql)
    write_file(query_path, final_sql)
