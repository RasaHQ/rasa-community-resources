"""First check for the router restart helper. It reads files and runs nothing the helper wrote.

It looks at the command the helper records for a restart, not at what the helper says.

  python3 check_helper.py PATH

PATH is the Mantle helper's tools.py, or a flows YAML file. Exit 0
when every command found for a restart is REBOOT, 1 when one is not, 2 when no command
could be found, so a missing command is never read as a pass.
"""
import ast
import re
import sys

EXPECTED = "REBOOT"


def commands_from_python(text):
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "OPERATIONS" for t in node.targets):
            table = ast.literal_eval(node.value)
            if isinstance(table, dict) and "restart" in table:
                return [str(table["restart"])]
    return []


def commands_from_yaml(text):
    return re.findall(r"command_sent\s*:\s*[\"']?([A-Za-z_]+)[\"']?", text)


def main(argv):
    if len(argv) != 2:
        print("usage: check_helper.py PATH")
        return 2
    try:
        text = open(argv[1], encoding="utf-8").read()
        found = commands_from_python(text) if argv[1].endswith(".py") else commands_from_yaml(text)
    except (OSError, SyntaxError, ValueError) as error:
        print("could not check:", type(error).__name__)
        return 2
    if not found:
        print("could not check: no command for a restart was found in", argv[1])
        return 2
    wrong = [command for command in found if command != EXPECTED]
    if wrong:
        print("FAIL: a restart records", ", ".join(sorted(set(wrong))), "and must record", EXPECTED)
        return 1
    print("PASS: a restart records", EXPECTED)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
