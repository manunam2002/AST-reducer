import sqlglot
from oracle import bug_still_exists

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def tokenize_sql(sql: str) -> list[str]:
    tokenizer = sqlglot.Tokenizer()
    tokens = tokenizer.tokenize(sql)
    return [token.text for token in tokens]


def untokenize_sql(tokens: list[str]) -> str:
    return " ".join(tokens)