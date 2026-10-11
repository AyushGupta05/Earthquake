"""Replay recovered immutable toy cells into a fresh local_runs directory only."""

import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import traceback


BASE = Path(__file__).resolve().parent
CELLS = (
    ("original_calculation_cell.py.txt", "ROOT"),
    ("original_warning_cell.py.txt", "root"),
    ("original_analytic_cases_cell.py.txt", "root"),
)
OUTPUTS = ("CALCULATIONS.json", "WARNING_CHECK.json", "ANALYTIC_CASES.json")
PINNED_NAMES = {"PROTOCOL.md", *OUTPUTS, *(name for name, _ in CELLS)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(base):
    """Reject changed source/protocol/reference bytes before reserving a run."""
    pins = json.loads((base / "reproduction_input_pins.json").read_text())
    if pins.get("version") != 1 or set(pins.get("files", {})) != PINNED_NAMES:
        raise ValueError("Unexpected reproduction pin schema or file set")
    for name, record in pins["files"].items():
        path = base / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Pinned input must be a regular file: {name}")
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError(f"Pinned input changed: {name}")
    return pins


def redirected_tree(source, root_name, output):
    """Replace only the historical top-level output-root assignment."""
    tree = ast.parse(source)
    roots = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == root_name
    ]
    if len(roots) != 1:
        raise ValueError("Historical cell must have exactly one output-root assignment")
    roots[0].value = ast.Call(
        func=ast.Name(id="Path", ctx=ast.Load()),
        args=[ast.Constant(value=str(output))], keywords=[],
    )
    return ast.fix_missing_locations(tree)


def load_math(base=BASE):
    """Load only original imports/constants/functions, never its event loop or writes."""
    verify_inputs(base)
    tree = ast.parse((base / CELLS[0][0]).read_text())
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "results"
            for target in node.targets
        ):
            break
        nodes.append(node)
    module = ast.Module(body=nodes, type_ignores=[])
    namespace = {"__name__": "recovered_toy_math"}
    exec(compile(module, CELLS[0][0], "exec"), namespace)
    return namespace


def semantic_value(name, value):
    """Ignore only runtime versions and their derived calculations-body SHA link."""
    result = copy.deepcopy(value)
    if name == "CALCULATIONS.json":
        result.pop("runtime", None)
    elif name == "WARNING_CHECK.json":
        result.pop("checked_calculations_sha256", None)
    return result


def first_difference(left, right, path="$" ):
    """Compare all scientific values exactly; no rounding/tolerance exclusions."""
    if type(left) is not type(right):
        return {"path": path, "reason": "type", "original": str(type(left)), "replay": str(type(right))}
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return {"path": path, "reason": "keys"}
        for key in left:
            difference = first_difference(left[key], right[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(left, list):
        if len(left) != len(right):
            return {"path": path, "reason": "length"}
        for index, (a, b) in enumerate(zip(left, right)):
            difference = first_difference(a, b, f"{path}[{index}]")
            if difference:
                return difference
    elif left != right:
        return {"path": path, "reason": "value", "original": left, "replay": right}
    return None


def compare_outputs(base, output):
    comparisons = {}
    for name in OUTPUTS:
        reference = json.loads((base / name).read_text())
        replay = json.loads((output / name).read_text())
        difference = first_difference(semantic_value(name, reference), semantic_value(name, replay))
        comparisons[name] = {
            "semantic_equal": difference is None,
            "first_difference": difference,
            "original_sha256": sha256(base / name),
            "replay_sha256": sha256(output / name),
            "byte_equal": (base / name).read_bytes() == (output / name).read_bytes(),
        }
    # A derived link is excluded only after verifying it points to its own bytes.
    for location in (base, output):
        warning = json.loads((location / "WARNING_CHECK.json").read_text())
        if warning["checked_calculations_sha256"] != sha256(location / "CALCULATIONS.json"):
            raise ValueError("Warning report does not bind its own calculation output")
    return comparisons


def run_reproduction(base, run_name):
    base = Path(base).resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_name):
        raise ValueError("Use a simple fresh run name, not a path")
    pins = verify_inputs(base)
    runs = base / "local_runs"
    if runs.is_symlink():
        raise ValueError("local_runs cannot be a symlink")
    output = runs / run_name
    # Compile all cells before creating output; their arithmetic bytes stay inert.
    programs = [
        (name, compile(redirected_tree((base / name).read_text(), root_name, output), name, "exec"))
        for name, root_name in CELLS
    ]
    runs.mkdir(exist_ok=True)
    output.mkdir()  # Existing directories/symlinks fail rather than overwrite.
    (output / "PROTOCOL.md").write_bytes((base / "PROTOCOL.md").read_bytes())
    receipt = {
        "kind": "Immutable recovered toy-cell reproduction; no training or data requests",
        "run_name": run_name,
        "input_pins": pins,
        "source_redirection": "AST replaces only the single historical ROOT/root assignment with this new output directory",
        "semantic_exclusions": {
            "CALCULATIONS.json": ["runtime"],
            "WARNING_CHECK.json": ["checked_calculations_sha256 (each own-body link verified)"],
            "ANALYTIC_CASES.json": [],
        },
        "status": "running",
    }
    failure = None
    try:
        for name, program in programs:
            stdout, stderr = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exec(program, {"__name__": "__main__", "__file__": name})
            finally:
                (output / f"{name}.stdout.txt").write_text(stdout.getvalue())
                (output / f"{name}.stderr.txt").write_text(stderr.getvalue())
        receipt["comparisons"] = compare_outputs(base, output)
        receipt["status"] = "pass" if all(
            result["semantic_equal"] for result in receipt["comparisons"].values()
        ) else "mismatch"
    except Exception:
        failure = traceback.format_exc()
        receipt["status"] = "failed"
        receipt["failure"] = failure
    # Preserve original output/source bytes even on an execution/comparison failure.
    verify_inputs(base)
    receipt["original_inputs_unchanged"] = True
    (output / "REPLAY_COMPARISON.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return output, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()
    output, receipt = run_reproduction(BASE, args.run_name)
    print(json.dumps({"output": str(output), "status": receipt["status"], "original_inputs_unchanged": receipt["original_inputs_unchanged"]}, indent=2))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
