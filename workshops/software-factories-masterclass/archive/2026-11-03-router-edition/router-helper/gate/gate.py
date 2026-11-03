"""The gate for the router helper. It judges one change the builder proposed. The builder cannot edit it.

  python3 gate.py CANDIDATE.py

The change must be a Python file that holds exactly one function, check_line_status(), which takes no arguments
and has one statement: return a dictionary written out as plain values. The gate reads the file once and judges
those bytes. It never runs the change, so the change cannot write a file, open the network, or do anything
else while it is judged. A change that needs more than a literal answer is rejected, and a person decides
what to do next. That fits this small read-only operation and is not a general sandbox.

Exit 0 ACCEPT, 1 REJECT (it prints the name of every test that failed), 2 could not judge.
"""
import ast
import sys
from pathlib import Path

EXPECTED = {"operation": "check_line_status", "status": "ok", "changes_anything": False}
FORBIDDEN_WORDS = ("REBOOT", "FACTORY_RESET")


def is_docstring(node):
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def failures_for(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return ["test_candidate_is_valid_python"]
    failures = []
    body = list(tree.body)
    if body and is_docstring(body[0]):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.FunctionDef) or body[0].name != "check_line_status":
        failures.append("test_only_the_one_function_and_nothing_else")
    else:
        function = body[0]
        arguments = function.args
        if (arguments.args or arguments.posonlyargs or arguments.kwonlyargs or arguments.vararg or arguments.kwarg
                or arguments.defaults or arguments.kw_defaults or function.decorator_list or function.returns):
            failures.append("test_takes_no_arguments_and_has_no_decorators")
        statements = list(function.body)
        if statements and is_docstring(statements[0]):
            statements = statements[1:]
        if len(statements) != 1 or not isinstance(statements[0], ast.Return) or statements[0].value is None:
            failures.append("test_body_is_one_return")
        else:
            try:
                value = ast.literal_eval(statements[0].value)
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                failures.append("test_returns_a_plain_literal")
            else:
                if value != EXPECTED:
                    failures.append("test_returns_the_expected_read_only_answer")
    if any(word in text for word in FORBIDDEN_WORDS):
        failures.append("test_no_restart_or_reset_command")
    return failures


def main(argv):
    if len(argv) != 2:
        print("usage: gate.py CANDIDATE.py")
        return 2
    try:
        text = Path(argv[1]).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print("could not judge:", type(error).__name__)
        return 2
    failures = failures_for(text)
    if failures:
        print("REJECT - failed:", ", ".join(failures))
        return 1
    print("ACCEPT - the change passed every check")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
