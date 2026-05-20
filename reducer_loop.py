import sqlglot

from sql_utils import read_file, write_file, tokenize_sql, untokenize_sql
from removal_helpers import remove_sql_statement, remove_insert_rows, reduce_clause_items
from oracle import bug_still_exists

oracle_cache = {}

def cached_bug_still_exists(candidate_sql: str, oracle_path: str) -> bool:
    key = candidate_sql.strip()

    if key in oracle_cache:
        return oracle_cache[key]

    result = bug_still_exists(candidate_sql, oracle_path)
    oracle_cache[key] = result
    return result

def parse_sql(sql: str):
    try:
        statements = sqlglot.parse(sql, read="sqlite")
        return [s for s in statements if s is not None]
    except Exception:
        return []

def reduce_query(query_path: str, oracle_path: str) -> None:
    sql = read_file(query_path)

    changed = True

    while changed:
        changed = False

        statements = parse_sql(sql)

        # Pass 1: remove one whole SQL statement at a time
        for candidate_sql in remove_sql_statement(statements):
            if cached_bug_still_exists(candidate_sql, oracle_path):
                print("Reduced sql statement")
                sql = candidate_sql
                changed = True
                break

        if changed:
            continue

        # Pass 2: reduce INSERT values
        for candidate_sql in remove_insert_rows(statements):
            if cached_bug_still_exists(candidate_sql, oracle_path):
                print("Reduced insert value")
                sql = candidate_sql
                changed = True
                break

        if changed:
            continue

        # # Pass 3: reduce WHERE/HAVING/GROUP BY/ORDER BY predicates
        # for candidate_sql in reduce_clause_items(statements):
        #     if cached_bug_still_exists(candidate_sql, oracle_path):
        #         print("Reduced clause item")
        #         sql = candidate_sql
        #         changed = True
        #         break

        # if changed:
        #     continue

    write_file(query_path, sql)