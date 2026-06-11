import sqlglot
from sqlglot import exp

from sql_utils import read_file, write_file, tokenize_sql#, untokenize_sqlove_sql_statement, remove_insert_rows, reduce_clause_items
from oracle import bug_still_exists

from removal_helpers import linear_reduce, get_stmt_targets, remove_stmt, get_clause_targets, remove_clause, get_leaf_targets, remove_leaf, get_binary_targets, remove_binary, get_unnest_targets, remove_unnest, get_constantizer_targets, remove_constantizer, ddmin_reduce, get_select_expr_targets, remove_select_expr, get_in_list_targets, remove_in_item, get_cte_targets, remove_cte, statements_to_sql, remove_sql_statement, remove_insert_rows, reduce_clause_items, get_insert_row_targets, remove_insert_row, get_insert_modifier_targets, remove_insert_modifier

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
        rendered = s.sql(dialect='sqlite', pretty=False).strip()
        if not rendered:
            continue
        result.append(s)
    return result

def reduce_query(query_path: str, reduced_query_path: str, oracle_path: str) -> None:
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

        ## Pass 1: remove one whole SQL statement at a time
        #for candidate_sql in remove_sql_statement(statements):
        #    if cached_bug_still_exists(candidate_sql, oracle_path):
        #        print("Reduced sql statement")
        #        sql = candidate_sql
        #        changed = True
        #        break
#
        #if changed:
        #    print(f"Current SQL:\n{statements_to_sql(statements)}")
        #    continue
#
        ## Pass 2: reduce INSERT values
        #for candidate_sql in remove_insert_rows(statements):
        #    if cached_bug_still_exists(candidate_sql, oracle_path):
        #        print("Reduced insert value")
        #        sql = candidate_sql
        #        changed = True
        #        break
#
        #if changed:
        #    print(f"Current SQL:\n{statements_to_sql(statements)}")
        #    continue
#
        ## Pass 3: reduce WHERE/HAVING/GROUP BY/ORDER BY predicates
        #for candidate_sql in reduce_clause_items(statements):
        #    if cached_bug_still_exists(candidate_sql, oracle_path):
        #        print("Reduced clause item")
        #        sql = candidate_sql
        #        changed = True
        #        break
#
        #if changed:
        #    print(f"Current SQL:\n{statements_to_sql(statements)}")
        #    continue

    final_sql = statements_to_sql(statements)
    print("Final reduced SQL:")
    print(final_sql)
    write_file(reduced_query_path, final_sql)