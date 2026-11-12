import ast
from pathlib import Path
import unittest

SEVEN = {"banking_accounts", "banking_balance", "banking_history", "banking_loan_payment",
         "banking_payoff", "banking_review_transfer", "banking_transfer_status"}
SERVER = Path(__file__).resolve().parents[1] / "silverlake_demo" / "server.py"


class ToolSurface(unittest.TestCase):
    def test_the_mcp_server_registers_exactly_the_seven_curated_tools(self):
        tree = ast.parse(SERVER.read_text())
        registered = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool"
                              for d in node.decorator_list)}
        self.assertEqual(registered, SEVEN)

    def test_confirm_submit_and_identity_are_not_mcp_tools(self):
        source = SERVER.read_text()
        for name in ("submit", "confirm", "assure", "open_session", "reset"):
            self.assertNotIn(f'def banking_{name}', source)
        self.assertEqual(set(__import__("re").findall(r'"(banking_\w+)": ', source)), SEVEN)


if __name__ == "__main__":
    unittest.main()
