import argparse
from reducer_logic import reduce_query


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--test", required=True)

    args = parser.parse_args()

    reduce_query(args.query, args.test)


if __name__ == "__main__":
    main()