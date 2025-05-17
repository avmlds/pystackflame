import logging
import re
from collections import defaultdict
from collections.abc import Generator
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


def is_traceback_start_line(line: str) -> bool:
    return TRACEBACK_ERROR_START_LINE.match(line) is not None


def get_traceback_error_stack_line(line: str) -> re.Match | None:
    return TRACEBACK_ERROR_STACK_LINE.match(line)


def is_traceback_end_line(line: str) -> bool:
    return TRACEBACK_ERROR_END_LINE.match(line) is not None


def prepare_trace_filter(trace_filter: str | None) -> list[str]:
    if trace_filter is None:
        return []

    if not trace_filter.startswith(TRACE_FILTER_DELIMITER):
        raise ValueError(f"Filter must start with a {TRACE_FILTER_DELIMITER}")

    if trace_filter.endswith(TRACE_FILTER_DELIMITER):
        raise ValueError(f"Filter cannot end on a {TRACE_FILTER_DELIMITER}")

    return [TRACE_FILTER_DELIMITER, *trace_filter.split(TRACE_FILTER_DELIMITER)[1:]]


def filter_trace_path(trace_path: list[str], trace_filter_list: list[str]):
    if len(trace_path) < len(trace_filter_list):
        return []

    trace_pointer = 0
    for trace_filter in trace_filter_list:
        if trace_filter == trace_path[trace_pointer] or trace_filter == WILDCARD_FILTER:
            trace_pointer += 1
        else:
            return []

    return trace_path[trace_pointer:]


def error_generator(file: TextIO) -> Generator[tuple[Path, int, str]]:
    in_frame = False
    for line in file:
        if not in_frame:
            in_frame = is_traceback_start_line(line)

        if not in_frame:
            continue

        if in_frame:
            stack_line = get_traceback_error_stack_line(line)
            if stack_line is None:
                continue

            path, line_number, python_object_name = stack_line.groups()
            yield Path(path), int(line_number), python_object_name

        if in_frame:
            in_frame = not is_traceback_end_line(line)


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


def build_log_graph(files: list[Path], trace_filter: str | None) -> rx.PyDiGraph:
    issue_graph = rx.PyDiGraph()
    node_graph_id_dict = {}
    edge_graph_id_dict = defaultdict(int)
    trace_filter_list = prepare_trace_filter(trace_filter)
    for path in files:
        try:
            with open(path, encoding=DEFAULT_ENCODING) as file:
                for error in error_generator(file):
                    file_path, row_number, python_object_name = error
                    path_parts = filter_trace_path(
                        list(file_path.parts),
                        trace_filter_list,
                    )
                    if not path_parts:
                        logger.info(
                            "Skipping path '%s' as it doesn't match trace filter '%s'",
                            error[0],
                            trace_filter,
                        )
                        continue

                    path_parts.append(python_object_name)
                    enrich_issue_graph(
                        issue_graph=issue_graph,
                        path_parts=path_parts,
                        node_graph_id_dict=node_graph_id_dict,
                        edge_graph_id_dict=edge_graph_id_dict,
                    )

        except FileNotFoundError:
            logger.error("Warning: cannot open %s", path)

    for (from_node_name, to_node_name), weight in edge_graph_id_dict.items():
        from_node = node_graph_id_dict[from_node_name]
        to_node = node_graph_id_dict[to_node_name]
        issue_graph.add_edge(from_node, to_node, {"weight": weight})

    return issue_graph


def build_flame_chart_data(files: list[Path], trace_filter: str | None) -> dict[tuple[str, ...], int]:
    flame_chart_dict = defaultdict(int)
    trace_filter_list = prepare_trace_filter(trace_filter)
    for path in files:
        try:
            with path.open("r") as file:
                for error in error_generator(file):
                    path_parts = filter_trace_path(
                        list(error[0].parts),
                        trace_filter_list,
                    )
                    if not path_parts:
                        logger.info(
                            "Skipping path '%s' as it doesn't match trace filter '%s'",
                            error[0],
                            trace_filter,
                        )
                        continue

                    full_path = tuple([*path_parts, error[2]])
                    flame_chart_dict[full_path] += 1

        except FileNotFoundError:
            logger.error("Warning: cannot open %s", path)

    return flame_chart_dict
