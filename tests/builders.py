import pytest

from pystackflame.builders import (
    _get_traceback_error_stack_line,
    _is_traceback_end_line,
    _is_traceback_start_line,
    _prepare_filter,
    _trace_path_is_excluded,
    build_trace_path_excludes,
    filter_trace_path,
    get_filtered_error_trace,
)


def test_is_traceback_start_line():
    assert _is_traceback_start_line("Traceback (most recent call last):")
    assert not _is_traceback_start_line('File "main.py", line 2, in <module>')


def test_get_traceback_error_stack_line():
    match = _get_traceback_error_stack_line('  File "main.py", line 42, in my_func')
    assert match is not None
    assert match.group(1) == "main.py"
    assert match.group(2) == "42"
    assert match.group(3) == "my_func"

    assert _get_traceback_error_stack_line("invalid line") is None


def test_is_traceback_end_line():
    assert _is_traceback_end_line("Exception: something went wrong")
    assert not _is_traceback_end_line('  File "main.py", line 42, in my_func')


def test_prepare_filter_valid():
    result = _prepare_filter("/a/b/c")
    assert result == ["/", "a", "b", "c"]


def test_prepare_filter_none():
    assert _prepare_filter(None) == []


def test_prepare_filter_invalid_start():
    with pytest.raises(ValueError):
        _prepare_filter("a/b/c")


def test_prepare_filter_invalid_end():
    with pytest.raises(ValueError):
        _prepare_filter("/a/b/c/")


def test_build_trace_path_excludes():
    excludes = build_trace_path_excludes(["/a/b", "/c"])
    assert excludes == [["/", "a", "b"], ["/", "c"]]


def test_filter_trace_path_matches():
    assert filter_trace_path(["/", "a", "b", "c"], ["/", "a"]) == ["b", "c"]


def test_filter_trace_path_no_match():
    assert filter_trace_path(["/", "a", "b"], ["/", "x"]) is None


def test_filter_trace_path_full_match():
    assert filter_trace_path(["/", "a", "b"], ["/", "a", "b"]) == []


def test_filter_trace_path_longer_filter():
    assert filter_trace_path(["/", "a", "b"], ["/", "a", "b", "c"]) is None


def test_filter_trace_path_wildcard():
    assert filter_trace_path(["/", "a", "b", "c"], ["/", "*", "b"]) == ["c"]


def test_trace_path_is_excluded_true():
    path = ["/", "a", "b", "c"]
    excludes = [["/", "a", "b"]]
    assert _trace_path_is_excluded(path, excludes)


def test_trace_path_is_excluded_false():
    path = ["/", "x", "y"]
    excludes = [["/", "a", "b"]]
    assert not _trace_path_is_excluded(path, excludes)


def test_get_filtered_error_trace_valid():
    path = ["/", "a", "b", "c"]
    include = ["/", "a"]
    excludes = [["/", "x", "y"]]
    assert get_filtered_error_trace(path, include, excludes) == ["b", "c"]


def test_get_filtered_error_trace_filtered_out():
    path = ["/", "a", "b", "c"]
    include = ["/", "a"]
    excludes = [["/", "a", "b"]]
    assert get_filtered_error_trace(path, include, excludes) is None


def test_get_filtered_error_trace_no_match():
    path = ["/", "x", "y"]
    include = ["/", "a"]
    excludes = []
    assert get_filtered_error_trace(path, include, excludes) is None
