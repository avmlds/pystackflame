import logging
import re
from collections import defaultdict
from collections.abc import Generator, Iterable
from pathlib import Path
from typing import TextIO

import rustworkx as rx

from pystackflame.constants import (
    DEFAULT_ENCODING,
    TRACE_FILTER_DELIMITER,
    TRACEBACK_ERROR_END_LINE,
    TRACEBACK_ERROR_STACK_LINE,
    TRACEBACK_ERROR_START_LINE,
    WILDCARD_FILTER,
)

logger = logging.getLogger(__name__)


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
    for exclude_path in exclude_paths:
        if filter_trace_path(trace_path_parts, exclude_path) is not None:
            return True

    return False


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


def error_generator(file: TextIO) -> Generator[tuple[Path, int, str]]:
    in_frame = False
    for line in file:
        if not in_frame:
            in_frame = _is_traceback_start_line(line)

        if not in_frame:
            continue

        if in_frame:
            stack_line = _get_traceback_error_stack_line(line)
            if stack_line is None:
                continue

            path, line_number, python_object_name = stack_line.groups()
            yield Path(path), int(line_number), python_object_name

        if in_frame:
            in_frame = not _is_traceback_end_line(line)


def enrich_issue_graph(
    issue_graph: rx.PyDiGraph,
    path_parts: list[str],
    node_graph_id_dict: dict[str, int],
    edge_graph_id_dict: dict[tuple[str, str], int],
) -> None:
    parent = path_parts[0]
    if parent not in node_graph_id_dict:
        node_graph_id_dict[parent] = issue_graph.add_node({"name": parent})

    for path_part in path_parts[1:]:
        if path_part not in node_graph_id_dict:
            node_graph_id_dict[path_part] = issue_graph.add_node({"name": path_part})

        key = (parent, path_part)
        edge_graph_id_dict[key] += 1
        parent = path_part


def read_errors(file_paths: list[Path]) -> Generator[tuple[Path, int, str]]:
    for path in file_paths:
        try:
            with open(path, encoding=DEFAULT_ENCODING) as file:
                yield from error_generator(file)

        except FileNotFoundError:
            logger.error("Cannot open %s", path)


def build_log_graph(
    files: list[Path],
    trace_filter: str | None,
    trace_path_excludes: list[list[str]],
) -> rx.PyDiGraph:
    issue_graph = rx.PyDiGraph()
    node_graph_id_dict = {}
    edge_graph_id_dict = defaultdict(int)
    trace_filter_list = _prepare_filter(trace_filter)

    for file_path, row_number, python_object_name in read_errors(files):
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

        enrich_issue_graph(
            issue_graph=issue_graph,
            path_parts=filtered_error_trace_path_parts,
            node_graph_id_dict=node_graph_id_dict,
            edge_graph_id_dict=edge_graph_id_dict,
        )

    for (from_node_name, to_node_name), weight in edge_graph_id_dict.items():
        from_node = node_graph_id_dict[from_node_name]
        to_node = node_graph_id_dict[to_node_name]
        issue_graph.add_edge(from_node, to_node, {"weight": weight})

    return issue_graph


def build_flame_chart_data(
    files: list[Path],
    trace_filter: str | None,
    trace_path_excludes: list[list[str]],
) -> dict[tuple[str, ...], int]:
    flame_chart_dict = defaultdict(int)
    trace_filter_list = _prepare_filter(trace_filter)

    for file_path, row_number, python_object_name in read_errors(files):
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
