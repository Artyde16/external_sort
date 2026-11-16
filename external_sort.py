"""Внешняя сортировка текстовых файлов (txt, csv):

Реализованые алгоритмы:
    1. external_natural_merge_sort   - естественное слияние
    2. external_balanced_merge_sort  - двухпутевое сбалансированное слияние
    3. external_nway_merge_sort      - N-путевое слияние
    4. external_polyphase_sort       - многофазная (Фибоначчиева) сортировка
    5. external_cascade_merge_sort   - каскадное слияние

"""

from typing import Callable

from common import (
    Options,
    Tape,
    Workspace,
    count_runs,
    distribute,
    merge_to,
    run_sort,
)


def _balanced(
    ws: Workspace, runs: Tape, keyf: Callable, ways: int, reverse: bool
) -> Tape:
    """Сбалансированное слияние: `ways` входных лент и `ways` выходных.

    Каждый проход сливает серии со входных лент по кругу в выходные,
    потом ленты меняются ролями. Заканчиваем, когда осталась одна серия.
    """
    ins = [ws.new_tape() for _ in range(ways)]
    outs = [ws.new_tape() for _ in range(ways)]
    distribute(runs, ins)
    while count_runs(ins) > 1:
        for tape in ins:
            tape.open_read()
        for tape in outs:
            tape.open_write()
        j = 0
        while count_runs(ins) > 0:
            merge_to([t for t in ins if t.runs], outs[j], keyf, reverse)
            j = (j + 1) % ways
        ins, outs = outs, ins
    return next((tape for tape in ins if tape.runs), ins[0])


def _natural_algo(ws: Workspace, runs: Tape, keyf: Callable, opts: Options) -> Tape:
    """Естественное слияние = двухпутевое слияние естественных серий."""
    return _balanced(ws, runs, keyf, 2, opts.reverse)


def _balanced_algo(ws: Workspace, runs: Tape, keyf: Callable, opts: Options) -> Tape:
    """Двухпутевое сбалансированное слияние отсортированных блоков."""
    return _balanced(ws, runs, keyf, 2, opts.reverse)


def _nway_algo(ws: Workspace, runs: Tape, keyf: Callable, opts: Options) -> Tape:
    """N-путевое слияние: сливаем сразу ways серий."""
    return _balanced(ws, runs, keyf, max(2, opts.ways), opts.reverse)


def _polyphase_algo(ws: Workspace, runs: Tape, keyf: Callable, opts: Options) -> Tape:
    """Многофазная сортировка на трех лентах.

    Серии раскладываются по числам Фибоначчи (F(k+1) и F(k)), недостающие
    добавляются пустышками. Затем сливаем две ленты в третью, пока одна из
    них не опустеет; опустевшая лента становится выходной.
    """
    tapes = [ws.new_tape() for _ in range(3)]
    big, small = 1, 0
    while big + small < len(runs.runs):
        big, small = big + small, big
    distribute(runs, tapes, [big, small, 0])

    while count_runs(tapes) > 1:
        ins = [tape for tape in tapes if tape.runs]
        out = next(tape for tape in tapes if not tape.runs)
        for tape in ins:
            if tape.mode != "r":
                tape.open_read()
        out.open_write()
        for _ in range(min(len(tape.runs) for tape in ins)):
            merge_to(ins, out, keyf, opts.reverse)
    return next((tape for tape in tapes if tape.runs), tapes[0])


def _cascade_algo(ws: Workspace, runs: Tape, keyf: Callable, opts: Options) -> Tape:
    """Каскадное слияние на k входных лентах + одной выходной (k = ways).

    Серии раскладываются по «идеальным» числам каскадного слияния
    (для k=3: 1,1,1 -> 3,2,1 -> 6,5,3 -> ...). Один проход (каскад):
    сначала сливаем серии со всех k лент, пока не опустеет самая короткая,
    потом со всех оставшихся (k-1), и так до одной ленты.
    """
    k = max(2, opts.ways)
    tapes = [ws.new_tape() for _ in range(k + 1)]
    levels = [1] + [0] * (k - 1)
    while sum(levels) < len(runs.runs):
        levels = [sum(levels[: k - i]) for i in range(k)]
    distribute(runs, tapes, levels + [0])

    while count_runs(tapes) > 1:
        inputs = [tape for tape in tapes if tape.runs]
        while len(inputs) >= 2:
            out = next(tape for tape in tapes if not tape.runs)
            for tape in inputs:
                if tape.mode != "r":
                    tape.open_read()
            out.open_write()
            for _ in range(min(len(tape.runs) for tape in inputs)):
                merge_to(inputs, out, keyf, opts.reverse)
            inputs = [tape for tape in inputs if tape.runs]
    return next((tape for tape in tapes if tape.runs), tapes[0])


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments


def external_natural_merge_sort(
    src,
    output=None,
    reverse=False,
    key="",
    type_data="s",
    ways=2,
    bsize=None,
) -> None:
    """Сортировка естественным слиянием (блоки не нужны, bsize не используется)."""
    run_sort(
        src,
        output,
        reverse,
        key,
        type_data,
        ways,
        bsize,
        _natural_algo,
        True,
    )


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments


def external_balanced_merge_sort(
    src,
    output=None,
    reverse=False,
    key="",
    type_data="s",
    ways=2,
    bsize=None,
) -> None:
    """Двухпутевая сбалансированная сортировка слиянием."""
    run_sort(
        src,
        output,
        reverse,
        key,
        type_data,
        ways,
        bsize,
        _balanced_algo,
        False,
    )


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments


def external_nway_merge_sort(
    src,
    output=None,
    reverse=False,
    key="",
    type_data="s",
    ways=3,
    bsize=None,
) -> None:
    """N-путевая сортировка слиянием (N = ways)."""
    run_sort(src, output, reverse, key, type_data, ways, bsize, _nway_algo, False)


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments


def external_polyphase_sort(
    src,
    output=None,
    reverse=False,
    key="",
    type_data="s",
    ways=2,
    bsize=None,
) -> None:
    """Многофазная (Фибоначчиева) сортировка на трех лентах."""
    run_sort(
        src,
        output,
        reverse,
        key,
        type_data,
        ways,
        bsize,
        _polyphase_algo,
        False,
    )


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments


def external_cascade_merge_sort(
    src,
    output=None,
    reverse=False,
    key="",
    type_data="s",
    ways=3,
    bsize=None,
) -> None:
    """Каскадная сортировка слиянием (ways - число входных лент)."""
    run_sort(
        src,
        output,
        reverse,
        key,
        type_data,
        ways,
        bsize,
        _cascade_algo,
        False,
    )


# pylint: enable=too-many-arguments


ALGORITHMS = {
    "natural": external_natural_merge_sort,
    "balanced": external_balanced_merge_sort,
    "nway": external_nway_merge_sort,
    "polyphase": external_polyphase_sort,
    "cascade": external_cascade_merge_sort,
}
