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
- `reducer_loop.py`
- `oracle.py`
- `utils.py`
- `removal_helpers.py`
- `reduction_passes.py`
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
  reducer --query queries/query1/original_test.sql --test queries/query1/test.sh
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
            --test "${d}test.sh";

    echo;
done
```
