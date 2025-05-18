# pystackflame

**Generate flamecharts from Python stacktraces in logs**

`pystackflame` is a command-line tool that parses Python logs for stack traces and turns them into flamecharts or weighed graphs for performance analysis, visualization, and debugging.

---

## Features

- Generate [FlameGraph](https://github.com/brendangregg/FlameGraph)-compatible output
- Pickle [rustworkx](https://github.com/Qiskit/rustworkx)-based graphs
- Build weighted execution graphs from logs using `rustworkx`
- Python 3.14+ support
- Fast and lightweight CLI built with `click`
- Developer-friendly with optional linting via `ruff`

---

## Installation

We recommend using [`uv`](https://github.com/astral-sh/uv) for fast dependency management:

```bash
uv sync -p 3.14
source .venv/bin/activate
pystackflame --help
```

## Possible applications

### Web Service Error Hotspots
Aggregate Python exceptions in your web server (e.g. Flask/FastAPI/Django) logs to quickly pinpoint which request-handling paths are failing most often without any need of restarting your application.
```shell 
pystackflame flame /var/log/myapp/**/*.log -o web_errors.flame
```
### Analysis of the historical data
Identify problematic places in the codebase that require the most attention.
```shell 
pystackflame flame /var/log/all_logs_we_have/**/*.log -o errors.flame
./flamegraph.pl errors.flame > example.svg
```

### Performance Regression Detection in CI
As part of your GitHub Actions or GitLab CI pipeline, run against the previous and current test logs to compare flamecharts—spot new slow-paths introduced by recent commits.
```shell
pystackflame flame old_tests.log -o baseline.flame
pystackflame flame new_tests.log -o current.flame
```
Visualize of diff the two SVGs or flame files to analyze regressions

### Batch-Job Profiling
For long-running data-processing jobs (ETL, ML training, batch analytics), collect stacktraces on failure or periodically dump traces, then visualize the cumulative “hot” stacks to optimize slow stages.
```shell
pystackflame flame /logs/batch_job_*.log -o batch_profile.flame
```

### Chaos-Engineering Fault Analysis
During fault-injection experiments, collect and compare flamecharts from healthy vs. faulted runs to understand how injected errors propagate.
```shell
pystackflame flame healthy.log -o healthy.flame
pystackflame flame chaos.log   -o chaos.flame
```

## Advanced filtering

You can specify an option 
`--trace-filter / -tf [PATH_PREFIX]`
to filter tracebacks to include only those paths that start with the given prefix and 
filter out the prefix out from the output. This is useful to restrict the flamechart or 
graph output to only relevant code paths with relevant names.

Additionally, you can specify multiple `--exclude / -e [PATH_PREFIX]` to exclude traces 
that starts from the given path prefix. Wildcard is supported as well.

### Example
This command 
```shell
pystackflame flame ~/test.log -tf '/opt/app/venv/lib64/python3.9/site-packages' 
```
Will produce the following flame data output
```
package;database;session.py;wrapper 2
package;apihelper.py;_make_request 2
package;apihelper.py;_check_result 2
```
And this command
```shell
pystackflame flame ~/test.log
```
Will give you this
```shell
/;opt;app;venv;lib64;python3.9;site-packages;package;database;session.py;wrapper 2
/;opt;app;venv;lib64;python3.9;site-packages;package;apihelper.py;_make_request 2
/;opt;app;venv;lib64;python3.9;site-packages;package;apihelper.py;_check_result 2
```
However, this command
```shell
pystackflame flame ~/test.log -tf '/opt/app/venv/lib64/python3.9/site-packages/package/apihelper.py' 
```
Will produce the following output
```shell
_make_request 2
_check_result 2
```


### Usage
- The filter must start with `/` (absolute path).
- `*` can be used to match any folder (e.g., `/var/log/app-logs/dates/*/application`).
- The filter must not end with `/`.

### Result:
- Only stack trace frames that match the filter will be added to the flamechart or graph.
- Useful for narrowing down logs to project-specific code or a specific dependency tree.
