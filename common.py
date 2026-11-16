"""Общие части внешней сортировки: ленты, чтение файлов, серии, слияние."""

import csv
import heapq
import os
import pathlib
import shutil
import tempfile
from dataclasses import dataclass
from typing import (
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Union,
)

PathType = Union[str, pathlib.Path]

DEFAULT_BSIZE = 10
CONVERTERS = {"int": int, "float": float, "str": str}

# Ленты и настройки

class Tape:
    """«Лента» - временный файл, в котором лежат серии строк подряд.

    В списке `runs` хранятся длины серий (в строках), чтобы знать,
    где одна серия заканчивается и начинается следующая.
    Серия длиной 0 - пустая, она нужна многофазной и каскадной сортировке.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.file = None
        self.mode: Optional[str] = None
        self.runs: List[int] = []

    def open_read(self) -> None:
        """Открыть ленту на чтение с начала."""
        self.close()
        # pylint: disable-next=consider-using-with
        self.file = open(self.path, "r", encoding="utf-8")
        self.mode = "r"

    def open_write(self) -> None:
        """Открыть ленту на запись (старое содержимое стирается)."""
        self.close()
        # pylint: disable-next=consider-using-with
        self.file = open(self.path, "w", encoding="utf-8")
        self.mode = "w"
        self.runs = []

    def close(self) -> None:
        """Закрыть файл ленты, если он открыт."""
        if self.file is not None:
            self.file.close()
            self.file = None
            self.mode = None

    def read_run(self) -> Iterator[str]:
        """Взять следующую серию: вернуть итератор по ее строкам."""
        length = self.runs.pop(0)
        return self._read_lines(length)

    def _read_lines(self, length: int) -> Iterator[str]:
        """Прочитать `length` строк с текущей позиции."""
        for _ in range(length):
            yield self.file.readline()

    def write_run(self, lines: Iterable[str]) -> None:
        """Дописать в ленту новую серию из строк `lines`."""
        count = 0
        for line in lines:
            self.file.write(line)
            count += 1
        self.runs.append(count)

    def __str__(self):
        return str(self.runs)


class Workspace:
    """Временная папка с лентами. После работы все удаляется."""

    def __init__(self, debug=False) -> None:
        if debug:
            debug_dir = pathlib.Path("temp")
            debug_dir.mkdir(parents=True, exist_ok=True)
            self.directory = debug_dir.resolve()
        else:
            self.directory = tempfile.mkdtemp(prefix="ext_sort_")
        self.tapes: List[Tape] = []

    def new_tape(self) -> Tape:
        """Создать новую ленту."""
        path = os.path.join(self.directory, f"tape_{len(self.tapes)}.txt")
        tape = Tape(path)
        self.tapes.append(tape)
        return tape

    def cleanup(self) -> None:
        """Закрыть все ленты и удалить временную папку."""
        for tape in self.tapes:
            tape.close()
        shutil.rmtree(self.directory, ignore_errors=True)


@dataclass
class Options:
    """Настройки одного запуска сортировки."""

    reverse: bool
    key: Union[str, int]
    type_data: str
    ways: int
    bsize: int
    natural: bool


# Чтение исходных данных и ключ сортировки


def read_header(path: PathType) -> Optional[str]:
    """Прочитать первую строку (заголовок) csv-файла."""
    with open(path, "r", encoding="utf-8") as file:
        line = file.readline()
    if not line:
        return None
    return line if line.endswith("\n") else line + "\n"


def getlines(paths: Sequence[PathType], is_csv: bool) -> Iterator[str]:
    """Построчно читать данные всех файлов (заголовок csv пропускается)."""
    for path in paths:
        with open(path, "r", encoding="utf-8") as file:
            if is_csv:
                next(file, None)
            for line in file:
                if is_csv and not line.strip():
                    continue
                yield line if line.endswith("\n") else line + "\n"


def column_index(columns: List[str], key: Union[str, int]) -> int:
    """Найти номер столбца csv по имени или по номеру (с нуля)."""
    if key in columns:
        return columns.index(key)
    if str(key).isdigit() and int(key) < len(columns):
        return int(key)
    raise ValueError(f"В csv нет столбца {key!r}")


def make_key(
    type_data: str, key: Union[str, int], header: Optional[str], is_csv: bool
) -> Callable[[str], object]:
    """Построить функцию, которая по строке файла возвращает ключ сортировки."""
    convert = CONVERTERS.get(type_data)
    if convert is None:
        raise ValueError("type_data должен быть 'int', 'float' или 'str'")
    if not is_csv:
        return lambda line: convert(line.rstrip("\r\n"))
    if header is None:
        return lambda line: line
    if key == "" or key is None:
        raise ValueError("Для csv нужно указать ключ сортировки (столбец)")
    index = column_index(next(csv.reader([header])), key)
    return lambda line: convert(next(csv.reader([line]))[index])


def _natural_runs(
    lines: Iterable[str], tape: Tape, keyf: Callable, reverse: bool
) -> None:
    """Скопировать строки в ленту, запоминая границы естественных серий.

    Естественная серия - максимальный уже упорядоченный кусок подряд.
    """
    count = 0
    prev = None
    for line in lines:
        key = keyf(line)
        if count and ((key > prev) if reverse else (key < prev)):
            tape.runs.append(count)
            count = 0
        tape.file.write(line)
        count += 1
        prev = key
    if count:
        tape.runs.append(count)


def _block_runs(
    lines: Iterable[str], tape: Tape, keyf: Callable, opts: Options
) -> None:
    """Читать по `bsize` строк, сортировать в памяти, писать как серию."""
    block: List[str] = []
    for line in lines:
        block.append(line)
        if len(block) >= opts.bsize:
            tape.write_run(sorted(block, key=keyf, reverse=opts.reverse))
            block = []
    if block:
        tape.write_run(sorted(block, key=keyf, reverse=opts.reverse))


def make_runs(lines: Iterable[str], tape: Tape, keyf: Callable, opts: Options) -> None:
    """Разбить входные строки на серии и записать их в `tape`."""
    tape.open_write()
    if opts.natural:
        _natural_runs(lines, tape, keyf, opts.reverse)
    else:
        _block_runs(lines, tape, keyf, opts)


def count_runs(tapes: Sequence[Tape]) -> int:
    """Сколько всего серий (включая пустышки) лежит на лентах."""
    return sum(len(tape.runs) for tape in tapes)


def distribute(
    source: Tape,
    targets: Sequence[Tape],
    counts: Optional[Sequence[int]] = None,
) -> None:
    """Раздать серии из `source` по лентам `targets`.

    Без `counts` серии раздаются по кругу. С `counts` на i-ю ленту кладется
    ровно counts[i] серий; если настоящих серий не хватает, добавляются
    пустышки (серии длиной 0).
    """
    source.open_read()
    for tape in targets:
        tape.open_write()
    total = len(source.runs)
    limits = list(counts) if counts is not None else [total] * len(targets)
    index = 0
    for _ in range(total):
        while len(targets[index].runs) >= limits[index]:
            index = (index + 1) % len(targets)
        targets[index].write_run(source.read_run())
        index = (index + 1) % len(targets)
    if counts is not None:
        for tape, limit in zip(targets, limits):
            tape.runs.extend([0] * (limit - len(tape.runs)))


def merge_to(inputs: Sequence[Tape], out: Tape, keyf: Callable, reverse: bool) -> None:
    """Слить по одной серии с каждой входной ленты в одну серию на `out`.

    heapq.merge читает строки лениво, по одной с каждой ленты.
    """
    streams = [tape.read_run() for tape in inputs]
    out.write_run(heapq.merge(*streams, key=keyf, reverse=reverse))


def write_result(result: Tape, header: Optional[str], dst: PathType) -> None:
    """Записать отсортированную серию в `dst` (через временный файл)."""
    if result.mode != "r":
        result.open_read()
    tmp_path = f"{dst}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as out:
        if header:
            out.write(header)
        if result.runs:
            for line in result.read_run():
                out.write(line)
    os.replace(tmp_path, dst)


def sort_group(
    sources: Sequence[PathType],
    dst: PathType,
    algorithm: Callable,
    opts: Options,
) -> None:
    """Отсортировать файлы `sources` (как один набор данных) в файл `dst`."""
    suffixes = {pathlib.Path(path).suffix.lower() for path in sources}
    if len(suffixes) > 1:
        raise ValueError("Все файлы должны быть одного формата")
    is_csv = suffixes == {".csv"}
    header = read_header(sources[0]) if is_csv else None
    keyf = make_key(opts.type_data, opts.key, header, is_csv)

    workspace = Workspace()
    try:
        runs = workspace.new_tape()
        make_runs(getlines(sources, is_csv), runs, keyf, opts)
        result = algorithm(workspace, runs, keyf, opts)
        write_result(result, header, dst)
    finally:
        workspace.cleanup()


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
def run_sort(
    src: Union[PathType, Sequence[PathType]],
    output: Optional[PathType],
    reverse: bool,
    key: Union[str, int],
    type_data: str,
    ways: int,
    bsize: Optional[int],
    algorithm: Callable,
    natural: bool,
) -> None:
    """Общая часть всех публичных функций сортировки."""
    sources = [src] if isinstance(src, (str, pathlib.Path)) else list(src)
    if not sources:
        raise ValueError("Не указано ни одного файла")
    if bsize is not None and bsize < 1:
        raise ValueError("bsize должен быть положительным")
    opts = Options(reverse, key, type_data, ways, bsize or DEFAULT_BSIZE, natural)
    if output:
        sort_group(sources, output, algorithm, opts)
    else:
        for path in sources:
            sort_group([path], path, algorithm, opts)
