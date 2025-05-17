import logging
import re
from collections import defaultdict
from collections.abc import Generator
from pathlib import Path
from typing import TextIO

import rustworkx as rx

from pystackflame.constants import (
    DEFAULT_ENCODING,
    TRACEBACK_ERROR_END_LINE,
    TRACEBACK_ERROR_STACK_LINE,
    TRACEBACK_ERROR_START_LINE,
)

logger = logging.getLogger(__name__)


def is_traceback_start_line(line: str) -> bool:
    return TRACEBACK_ERROR_START_LINE.match(line) is not None


def get_traceback_error_stack_line(line: str) -> re.Match | None:
    return TRACEBACK_ERROR_STACK_LINE.match(line)


def is_traceback_end_line(line: str) -> bool:
    return TRACEBACK_ERROR_END_LINE.match(line) is not None


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
    error: tuple[Path, int, str],
    node_graph_id_dict: dict[str, int],
    edge_graph_id_dict: dict[tuple[str, str], int],
) -> None:
    file_path, row_number, python_object_name = error
    path_parts = list(file_path.parts)
    path_parts.append(python_object_name)

    parent = path_parts[0]
    if parent not in node_graph_id_dict:
        node_graph_id_dict[parent] = issue_graph.add_node({"name": parent})

    for path_part in path_parts[1:]:
        if path_part not in node_graph_id_dict:
            node_graph_id_dict[path_part] = issue_graph.add_node({"name": path_part})

        key = (parent, path_part)
        edge_graph_id_dict[key] += 1
        parent = path_part


def build_log_graph(files: list[Path]) -> rx.PyDiGraph:
    issue_graph = rx.PyDiGraph()
    node_graph_id_dict = {}
    edge_graph_id_dict = defaultdict(int)

    for path in files:
        try:
            with open(path, encoding=DEFAULT_ENCODING) as file:
                for error in error_generator(file):
                    enrich_issue_graph(
                        issue_graph=issue_graph,
                        error=error,
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


def build_flame_chart_data(files: list[Path]) -> dict[tuple[str, ...], int]:
    flame_chart_dict = defaultdict(int)
    for path in files:
        try:
            with path.open("r") as file:
                for error in error_generator(file):
                    full_path = tuple([*error[0].parts, error[2]])
                    flame_chart_dict[full_path] += 1

        except FileNotFoundError:
            logger.error("Warning: cannot open %s", path)

    return flame_chart_dict
