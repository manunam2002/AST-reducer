# AST SQLite Reducer Project

This project implements a small SQL test-case reducer for the AST database testing project.

## Build the Docker Image

The project uses the provided course image as its base image:

```dockerfile
FROM theosotr/sqlite3-reducer
```

This image already contains the required SQLite binaries:

```text
/usr/bin/sqlite3-3.26.0
/usr/bin/sqlite3-3.39.4
```

Build the reducer image from the project root:

```bash
docker build -t ast-reducer .
```

Rebuild the image whenever you change reducer code, for example:

- `main.py`
- `reducer_logic.py`
- `oracle.py`
- `sql_utils.py`
- `removal_helpers.py`
- `requirements.txt`
- `reducer`

You do not need to rebuild if you only change files inside `queries/`.

## Run the Reducer on ONE Query

From the project root:

```bash
docker run -it --platform linux/amd64 --rm \
  -v "$(pwd)":/workspace \
  -w /workspace \
  ast-reducer \
  reducer --query queries/query3/original_test.sql --reduced queries/query3/reduced_test.sql --test queries/query3/test.sh
```

The reducer modifies the file passed via `--query` in place. After the reducer finishes, `queries/query1/original_test.sql` contains the reduced query.

## Run the Reducer on ALL Queries

From the project root:

```bash
for d in queries/query*/; do
    echo "========================================";
    echo "Running reducer on $d";
    echo "========================================";

    docker run -it --rm \
        -v "$(pwd)":/workspace \
        -w /workspace \
        ast-reducer \
        reducer \
            --query "${d}original_test.sql" \
            --test "${d}test.sh" --reduced "${d}reduced_test.sql";

    echo;
done
```

## Reduction Passes

The reducer currently uses three structured reduction passes.

### Pass 1: Remove Whole SQL Statements

This pass removes one complete SQL statement at a time.

Example:

```sql
CREATE TABLE t0(a);
INSERT INTO t0 VALUES (1);
CREATE INDEX i0 ON t0(a);
SELECT * FROM t0;
```

Candidate:

```sql
CREATE TABLE t0(a);
INSERT INTO t0 VALUES (1);
SELECT * FROM t0;
```

### Pass 2: Reduce INSERT Rows

This pass reduces multi-row `INSERT ... VALUES`.

Example:

```sql
INSERT INTO t0 VALUES
  (1),
  (2),
  (3);
```

Candidate:

```sql
INSERT INTO t0 VALUES
  (1),
  (3);
```

### Pass 3: Reduce Clause Items

This pass simplifies parts of clauses such as:

- `WHERE`
- `HAVING`
- `GROUP BY`
- `ORDER BY`

For `WHERE` and `HAVING`, it tries to replace subexpressions with simpler boolean values such as `TRUE`.

For `ORDER BY` and `GROUP BY`, it tries to remove individual ordering or grouping expressions.

Example:

```sql
SELECT * FROM t0
WHERE a > 5 AND b < 10
ORDER BY a, b;
```

Possible candidates:

```sql
SELECT * FROM t0
WHERE TRUE AND b < 10
ORDER BY a, b;
```

or:

```sql
SELECT * FROM t0
WHERE a > 5 AND b < 10
ORDER BY a;
```

## TODOS

[ ] Pass 2 is insanely slow. Find a different approach that is faster. Its slow because of the amount of reduction steps.
[ ] Add Pass 4: replace expressions with: 0, 1, NULL, TRUE, FALSE
[ ] Add Pass 5: token ddmin cleanup
