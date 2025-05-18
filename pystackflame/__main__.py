import logging
import pickle
from datetime import datetime
from pathlib import Path

import click

from pystackflame.builders import build_flame_chart_data, build_log_graph, build_trace_path_excludes
from pystackflame.constants import DEFAULT_FLAME_CHART_FILENAME, DEFAULT_GRAPH_FILENAME

logger = logging.getLogger()


@click.group()
def cli():
    """Generate FlameGraph-compatible flame chart data and graphs from errors in logfiles."""
    pass


@click.option("-e", "--exclude", multiple=True, help="Exclude trace paths from the output")
@click.option("-tf", "--trace-filter", help="Filter trace paths by prefix. '*' stands for any folder.")
@click.option("-o", "--output", type=Path, default=DEFAULT_GRAPH_FILENAME)
@click.argument("log_files", type=Path, nargs=-1)
@cli.command()
def graph(log_files, output: Path, trace_filter: str | None):
    """Generate a pickled weighed rustworkx graph."""
    click.echo(f"{datetime.now()} Starting building log graph for: {log_files}")
    error_graph = build_log_graph(log_files, trace_filter)
    if error_graph.num_nodes() == 0:
        raise click.ClickException("Graph is empty, please check filters, if applied.")

    with output.open("wb") as file:
        pickle.dump(error_graph, file)

    click.echo(f"{datetime.now()} Done building log graph for: {log_files}")
    click.echo(f"{datetime.now()} Result saved at {output.expanduser().absolute()}")


@click.option("-e", "--exclude", multiple=True, help="Exclude trace paths from the output")
@click.option("-tf", "--trace-filter", help="Filter trace paths by prefix. '*' stands for any folder.")
@click.option("-o", "--output", type=Path, default=DEFAULT_FLAME_CHART_FILENAME)
@click.argument("log_files", type=Path, nargs=-1, required=True)
@cli.command("flame")
def flame_chart(log_files, output: Path, trace_filter: str | None, exclude: tuple[str]):
    """Generate standard flame chart data.

    Output is compatible with a visualization tool https://github.com/brendangregg/FlameGraph
    """
    click.echo(f"{datetime.now()} Starting preparing flame chart data for: {log_files}")
    trace_path_excludes = build_trace_path_excludes(exclude)
    errors_dict = build_flame_chart_data(
        log_files,
        trace_filter,
        trace_path_excludes,
    )
    if not errors_dict:
        raise click.ClickException("Flame chart data is empty, please check filters, if applied.")

    with output.open("w") as file:
        for error_path, n_errors in errors_dict.items():
            line = ";".join(error_path) + f" {n_errors}\n"
            file.write(line)

    click.echo(f"{datetime.now()} Done preparing flame chart data for: {log_files}")
    click.echo(f"{datetime.now()} Result saved at {output.expanduser().absolute()}")


if __name__ == "__main__":
    cli()
