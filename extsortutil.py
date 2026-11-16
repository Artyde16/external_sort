"""Консольная утилита внешней сортировки файлов txt и csv."""

import argparse
from typing import Optional, Sequence

from common import CONVERTERS
from external_sort import ALGORITHMS


def build_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Внешняя сортировка файлов txt и csv."
    )
    parser.add_argument(
        "algorithm", choices=sorted(ALGORITHMS), help="алгоритм сортировки"
    )
    parser.add_argument(
        "files", nargs="+", help="исходные файлы (один формат)"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="выходной файл; без него файлы сортируются на месте",
    )
    parser.add_argument(
        "-k", "--key", help="для csv: имя столбца или номер (с 0)"
    )
    parser.add_argument(
        "-t",
        "--type",
        dest="type_data",
        default="s",
        choices=sorted(CONVERTERS),
        help="тип сортируемых данных: int, float, str",
    )
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="сортировать по невозрастанию",
    )
    parser.add_argument(
        "--ways",
        type=int,
        default=3,
        help="число путей слияния (nway, cascade)",
    )
    parser.add_argument(
        "--bsize",
        type=int,
        default=None,
        help="размер блока в строках, хранимого в памяти",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Точка входа CLI."""
    args = build_parser().parse_args(argv)
    ALGORITHMS[args.algorithm](
        src=args.files,
        output=args.output,
        reverse=args.reverse,
        key=args.key or "",
        type_data=args.type_data,
        ways=args.ways,
        bsize=args.bsize,
    )


if __name__ == "__main__":
    main()
