"""Скрипт, вход и выход в одной папке: сырьё и производное вперемешку."""

import csv
import json
import sys


def main():
    rows = list(csv.reader(open("input.csv", encoding="utf-8")))
    json.dump(rows, open("output.json", "w", encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
