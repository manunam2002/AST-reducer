import time
import json
from pathlib import Path
import sqlglot
from utils import read_file
from reducer_loop import reduce_query

def count_ast_nodes(sql: str) -> int:
    try:
        stmts = sqlglot.parse(sql, read="sqlite", error_level=sqlglot.ErrorLevel.IGNORE)
        return sum(1 for s in stmts if s for _ in s.walk())
    except Exception:
        return 0

def count_statements(sql: str) -> int:
    try:
        return len([s for s in sqlglot.parse(sql, read="sqlite", error_level=sqlglot.ErrorLevel.IGNORE) if s])
    except Exception:
        return 0

def count_tokens(sql: str) -> int:
    try:
        return len(sqlglot.tokenize(sql, read="sqlite"))
    except Exception:
        return 0

def run_benchmarks(queries_dir: str, output_path: str):
    results = []
    queries_dir = Path(queries_dir)

    for benchmark_dir in sorted(queries_dir.iterdir()):
        if not benchmark_dir.is_dir():
            continue

        query_path = benchmark_dir / "original_test.sql"
        oracle_path = benchmark_dir / "test.sh"

        print(f"\nRunning benchmark: {benchmark_dir.name}")
        original_sql = read_file(query_path)
        start_time = time.time()

        reduce_query(str(query_path), str(oracle_path))

        elapsed = time.time() - start_time

        reduced_sql = read_file(query_path)

        orig_nodes = count_ast_nodes(original_sql)
        red_nodes = count_ast_nodes(reduced_sql)
        
        orig_tokens = count_tokens(original_sql)
        red_tokens = count_tokens(reduced_sql)

        result = {
            "name":              benchmark_dir.name,
            "original_tokens":   orig_tokens,
            "reduced_tokens":    red_tokens,
            "token_ratio":       red_tokens / max(orig_tokens, 1),
            "original_stmts":    count_statements(original_sql),
            "reduced_stmts":     count_statements(reduced_sql),
            "original_nodes":    orig_nodes,
            "reduced_nodes":     red_nodes,
            "node_ratio":        red_nodes / max(orig_nodes, 1),
            "elapsed_seconds":   round(elapsed, 2),
        }
        results.append(result)
        print(f"  tokens: {result['token_ratio']:.1%} | nodes: {result['node_ratio']:.1%} | time: {elapsed:.1f}s")
        
    print("\n=== SUMMARY ===")
    print(f"{'Benchmark':<30} {'Tokens%':>8} {'Nodes%':>7} {'Time':>8}")
    print("-" * 60)
    for r in results:
        print(f"{r['name']:<30} {r['token_ratio']:>8.1%} {r['node_ratio']:>7.1%} {r['elapsed_seconds']:>7.1f}s")

    if results:
        print("-" * 60)
        print(f"{'AVERAGE':<30}"
              f" {sum(r['token_ratio'] for r in results)/len(results):>8.1%}"
              f" {sum(r['node_ratio'] for r in results)/len(results):>7.1%}"
              f" {sum(r['elapsed_seconds'] for r in results)/len(results):>7.1f}s")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {output_path}")
    