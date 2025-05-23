import itertools
import logging
import re
from collections import defaultdict
from collections.abc import Generator, Iterable
from pathlib import Path
from typing import TextIO, TypeAlias

from pystackflame.constants import (
    DEFAULT_ENCODING,
    TRACE_FILTER_DELIMITER,
    TRACEBACK_ERROR_END_LINE,
    TRACEBACK_ERROR_STACK_LINE,
    TRACEBACK_ERROR_START_LINE,
    WILDCARD_FILTER,
)

logger = logging.getLogger(__name__)

EOS: TypeAlias = bool
"""End of stack."""


def _is_traceback_start_line(line: str) -> bool:
    return TRACEBACK_ERROR_START_LINE.match(line) is not None


def _get_traceback_error_stack_line(line: str) -> re.Match | None:
    return TRACEBACK_ERROR_STACK_LINE.match(line)


def _is_traceback_end_line(line: str) -> bool:
    return TRACEBACK_ERROR_END_LINE.match(line) is not None


def _prepare_filter(trace_filter: str | None) -> list[str]:
    if trace_filter is None:
        return []

    if not trace_filter.startswith(TRACE_FILTER_DELIMITER):
        raise ValueError(f"Filter must start with a {TRACE_FILTER_DELIMITER}")

    if trace_filter.endswith(TRACE_FILTER_DELIMITER):
        raise ValueError(f"Filter cannot end on a {TRACE_FILTER_DELIMITER}")

    return [TRACE_FILTER_DELIMITER, *trace_filter.split(TRACE_FILTER_DELIMITER)[1:]]


def build_trace_path_excludes(exclude_filters: Iterable[str]) -> list[list[str]]:
    return sorted(_prepare_filter(exclude_filter) for exclude_filter in exclude_filters)


def filter_trace_path(trace_path: list[str], trace_filter_list: list[str]) -> list[str] | None:
    if len(trace_path) < len(trace_filter_list):
        return None

    trace_pointer = 0
    for trace_filter in trace_filter_list:
        if trace_filter == trace_path[trace_pointer] or trace_filter == WILDCARD_FILTER:
            trace_pointer += 1
        else:
            return None

    return trace_path[trace_pointer:]


def _trace_path_is_excluded(trace_path_parts: list[str], exclude_paths: list[list[str]]) -> bool:
    return any(filter_trace_path(trace_path_parts, exclude_path) is not None for exclude_path in exclude_paths)


def get_filtered_error_trace(
    file_path_parts: list[str],
    trace_filter_list: list[str],
    trace_path_excludes: list[list[str]],
) -> list[str] | None:
    path_parts = filter_trace_path(
        file_path_parts,
        trace_filter_list,
    )
    if path_parts is None or _trace_path_is_excluded(file_path_parts, trace_path_excludes):
        return None

    return path_parts


def error_generator(file: TextIO) -> Generator[tuple[tuple[Path, int, str], EOS]]:
    in_frame = False
    last = None
    for line in file:
        if not in_frame:
            in_frame = _is_traceback_start_line(line)

        if not in_frame:
            continue

        stack_line = _get_traceback_error_stack_line(line)
        if stack_line is not None:
            path, line_number, python_object_name = stack_line.groups()
            last = Path(path), int(line_number), python_object_name
            yield last, False

        in_frame = _is_traceback_start_line(line) or not _is_traceback_end_line(line)
        if not in_frame and last is not None:
            yield last, True
            last = None


def read_errors(file_paths: tuple[Path]) -> Generator[tuple[tuple[Path, int, str], EOS]]:
    for path in file_paths:
        with path.open(encoding=DEFAULT_ENCODING) as file:
            yield from error_generator(file)


def build_log_graph(
    files: tuple[Path],
    trace_filter: str | None,
    trace_path_excludes: list[list[str]],
) -> dict[str, list[dict[str, str | int]]]:
    nodes = set()
    intensity_dict = defaultdict(int)
    edges = defaultdict(int)
    trace_filter_list = _prepare_filter(trace_filter)

    seen = defaultdict(int)
    for (file_path, _row_number, python_object_name), end_of_stack in read_errors(files):
        # When we are building graphs, we don't count EOS rows,
        # because we are more interested in the edge weights.
        if end_of_stack:
            for key, intensity in seen.items():
                intensity_dict[key] += intensity

            seen = defaultdict(int)
            continue

        file_path_parts = [*file_path.parts, python_object_name]
        filtered_error_trace_path_parts = get_filtered_error_trace(
            file_path_parts,
            trace_filter_list,
            trace_path_excludes,
        )
        if not filtered_error_trace_path_parts:
            logger.info(
                "Skipping path '%s' as it doesn't match trace filter '%s' or one of the exclude filters '%s'",
                file_path_parts,
                trace_filter,
                trace_path_excludes,
            )
            continue

        for parent, path_part in itertools.pairwise(filtered_error_trace_path_parts):
            nodes.add(parent)
            nodes.add(path_part)
            key = (parent, path_part)
            if key not in seen:
                edges[key] += 1
            seen[key] += 1

    return {
        "nodes": [{"id": node, "label": node} for node in nodes],
        "edges": [
            {
                "source": from_node,
                "target": to_node,
                "weight": weight,
                "intensity": intensity_dict[(from_node, to_node)],
            }
            for (from_node, to_node), weight in edges.items()
        ],
    }


def build_flame_chart_data(
    files: tuple[Path],
    trace_filter: str | None,
    trace_path_excludes: list[list[str]],
) -> dict[tuple[str, ...], int]:
    flame_chart_dict = defaultdict(int)
    trace_filter_list = _prepare_filter(trace_filter)

    for (file_path, _row_number, python_object_name), end_of_stack in read_errors(files):
        # When we are building flamegraph data, we are interested only in the last errors in the trace
        if not end_of_stack:
            continue

        file_path_parts = [*file_path.parts, python_object_name]
        filtered_error_trace_path_parts = get_filtered_error_trace(
            file_path_parts,
            trace_filter_list,
            trace_path_excludes,
        )
        if not filtered_error_trace_path_parts:
            logger.info(
                "Skipping path '%s' as it doesn't match trace filter '%s' or one of the exclude filters '%s'",
                file_path_parts,
                trace_filter,
                trace_path_excludes,
            )
            continue

        flame_chart_dict[tuple(filtered_error_trace_path_parts)] += 1

    return flame_chart_dict
