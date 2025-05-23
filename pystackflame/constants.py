import re

DEFAULT_ENCODING = "utf-8"
TRACEBACK_ERROR_START_LINE = re.compile(r"Traceback \(most recent call last\):")
TRACEBACK_ERROR_STACK_LINE = re.compile(r"\s+File\s\"(\S+)\",\sline\s(\d+),\sin\s<?(\w+)>?$")
TRACEBACK_ERROR_END_LINE = re.compile(r"^\S+")
DEFAULT_GRAPH_FILENAME = "error_graph.json"
DEFAULT_FLAME_CHART_FILENAME = "error_graph.flame"
WILDCARD_FILTER = "*"
TRACE_FILTER_DELIMITER = "/"
