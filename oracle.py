import os
import subprocess
import tempfile

def bug_still_exists(candidate_sql: str, oracle_path: str) -> bool:
    candidate_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sql",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(candidate_sql)
            candidate_path = f.name

        env = os.environ.copy()
        env["TEST_CASE_LOCATION"] = candidate_path

        result = subprocess.run(
            ["bash", oracle_path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        return False

    finally:
        if candidate_path is not None and os.path.exists(candidate_path):
            os.remove(candidate_path)
