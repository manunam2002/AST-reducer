from oracle import bug_still_exists
from sql_util import read_file, write_file, tokenize_sql, untokenize_sql
from removal_helpers import remove_sql_statement

def reduce_query(query_path: str, oracle_path: str) -> None:
    sql = read_file(query_path)

    changed = True

    while changed:
        changed = False

        # Pass 1: statement removal
        for candidate_sql in remove_sql_statement(sql):
            if bug_still_exists(candidate_sql, oracle_path):
                print(f"ACCEPT deletion")
                sql = candidate_sql
                write_file(query_path, sql)
                changed = True
                break

        if changed:
            continue

    write_file(query_path, sql)