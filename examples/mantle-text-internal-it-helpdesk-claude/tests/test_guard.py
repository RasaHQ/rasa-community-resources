"""Offline checks for the Orchard Works least-authority guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import helpdesk as hd  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "internal-it-helpdesk.json"
)
SPEC = PROJECT / "case-build" / "conversations.json"
ME = hd.SESSION_EMPLOYEE_ID
COLLEAGUE = "OW-E-3340"


def fresh() -> hd.HelpdeskService:
    return hd.HelpdeskService("test")


def ready(service: hd.HelpdeskService, words: str) -> dict:
    opened = hd.open_access_ticket(service, ME, words)
    assert opened["status"] == "ready_to_grant", opened
    return opened


def grant(service: hd.HelpdeskService, ticket_ref: str) -> dict:
    return hd.grant_access(service, ME, ticket_ref, ticket_ref, conversation_id="test")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), hd.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = hd.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                facts = variant["facts"]
                request = hd.evaluate(facts, "request", contract)
                expected = variant["expected"]
                if request:
                    self.assertEqual((expected["status"], request, expected["effects"]),
                                     ("blocked", expected["reason"], 0))
                    continue
                receipt = hd.evaluate(facts, "receipt", contract)
                self.assertEqual("pending" if receipt else "succeeded", expected["status"])
                self.assertEqual(receipt or "verified_fixture_receipt", expected["reason"])
                self.assertEqual(expected["effects"], 1)


class FictionalOrganisationTests(unittest.TestCase):
    def setUp(self):
        self.contract = hd.load_contract()

    def test_fixture_is_the_contracts_fictional_organisation(self):
        hd.assert_fictional(hd.load_data(), self.contract)
        self.assertEqual(hd.ORGANISATION, self.contract["organisation"])

    def test_only_the_casebook_organisation_is_allowed(self):
        """An allowlist: any other name is refused, marked fictional or not."""
        for value in ("Orchard Works", "Some Other Company (fictional)", "Orchard Holdings (fictional)"):
            data = hd.load_data()
            data["organisation"] = value
            with self.subTest(organisation=value), self.assertRaises(hd.FictionalOrganisationError):
                hd.assert_fictional(data, self.contract)

    def test_every_system_belongs_to_the_organisation(self):
        data = hd.load_data()
        data["roles"]["PAYROLL-ADMIN"]["system"] = "Acme Payroll"
        with self.assertRaises(hd.FictionalOrganisationError):
            hd.assert_fictional(data, self.contract)

    def test_email_must_be_on_the_reserved_domain(self):
        data = hd.load_data()
        data["employees"][ME]["email"] = "marisol.quint@orchardworks.com"
        with self.assertRaises(hd.FictionalOrganisationError):
            hd.assert_fictional(data, self.contract)
        data = hd.load_data()
        data["email_domain"] = "orchardworks.com"
        with self.assertRaises(hd.FictionalOrganisationError):
            hd.assert_fictional(data, self.contract)

    def test_note_and_case_must_match(self):
        data = hd.load_data()
        data["note"] = "Sample data."
        with self.assertRaises(hd.FictionalOrganisationError):
            hd.assert_fictional(data, self.contract)
        data = hd.load_data()
        data["case_slug"] = "step-up-authentication"
        with self.assertRaises(hd.FictionalOrganisationError):
            hd.assert_fictional(data, self.contract)


class MemoryValueTests(unittest.TestCase):
    def test_every_memory_value_fits_mantles_limit(self):
        """Mantle renders at most 100 characters of a memory value, silently."""
        values = dict(hd.session_profile())
        service = fresh()
        for role_ref in service.roles:
            ticket_ref = f"IT-TKT-9{len(values):04d}"
            service.tickets[ticket_ref] = {"employee": ME, "role": role_ref, "access_expires": "2027-12-31"}
            for key, value in hd.memory_values(service, ticket_ref).items():
                values[f"{role_ref}:{key}"] = value
        for key, value in values.items():
            with self.subTest(key=key):
                self.assertLess(len(str(value)), hd.MEMORY_VALUE_LIMIT, value)

    def test_open_ticket_writes_short_values(self):
        service = fresh()
        opened = ready(service, "viewer on finance reporting")
        memory = hd.memory_values(service, opened["ticket_ref"])
        self.assertEqual(memory["selected_scope_label"], "Finance Reporting viewer until 2026-12-31")
        self.assertTrue(all(len(v) < hd.MEMORY_VALUE_LIMIT for v in memory.values()))


class ResolveRoleTests(unittest.TestCase):
    def test_words_to_roles(self):
        service = fresh()
        cases = {
            "viewer access to the finance reporting dashboards": "FIN-REPORTS-VIEW",
            "edit rights in finance reporting": "FIN-REPORTS-EDIT",
            "payroll admin": "PAYROLL-ADMIN",
            "admin on the payroll console": "PAYROLL-ADMIN",
            "temporary global admin": "DIRECTORY-ADMIN",
            "production database admin": "PROD-DB-ADMIN",
            "analyst access on the data warehouse": "DW-ANALYST",
            "upload to the design library": "DESIGN-LIB-CONTRIB",
            "FIN-REPORTS-VIEW": "FIN-REPORTS-VIEW",
        }
        for words, expected in cases.items():
            with self.subTest(words=words):
                self.assertEqual(service.resolve_role(words), (expected, []))

    def test_level_not_named_gives_candidates(self):
        role, candidates = fresh().resolve_role("access to finance reporting")
        self.assertIsNone(role)
        self.assertEqual(candidates, ["FIN-REPORTS-EDIT", "FIN-REPORTS-VIEW"])

    def test_unknown_system(self):
        self.assertEqual(fresh().resolve_role("the coffee machine"), (None, []))


class IntakeTests(unittest.TestCase):
    def test_owner_approved_scope_is_ready(self):
        opened = ready(fresh(), "viewer on finance reporting")
        self.assertEqual((opened["role_ref"], opened["approval_ref"], opened["access_changed"]),
                         ("FIN-REPORTS-VIEW", "OW-APR-51207", False))
        self.assertTrue(re.fullmatch(r"IT-TKT-\d{5}", opened["ticket_ref"]))

    def test_manager_endorsement_is_not_approval(self):
        service = fresh()
        opened = hd.open_access_ticket(service, ME, "payroll admin", business_reason="urgent, my manager said ok")
        self.assertEqual((opened["status"], opened["reason"], opened["approval_problem"]),
                         ("awaiting_approval", "scope_unapproved", "manager_endorsement_is_not_owner_approval"))
        self.assertIn("Urgency does not change who authorizes access", opened["next_step"])
        self.assertEqual(opened["waiting_on"], "Payroll Systems owner")
        self.assertNotIn("PAYROLL-ADMIN", service.access(ME))

    def test_expired_and_missing_approvals(self):
        for words, problem in (("crm export", "approval_expired"), ("editor on finance reporting",
                                                                       "no_approval_on_record"),
                               ("global admin", "no_approval_on_record"),
                               ("production database admin", "no_approval_on_record")):
            with self.subTest(words=words):
                opened = hd.open_access_ticket(fresh(), ME, words)
                self.assertEqual((opened["status"], opened["approval_problem"]), ("awaiting_approval", problem))
                self.assertTrue(opened["approval_request_ref"].startswith("OW-APRQ-"))

    def test_colleagues_approval_does_not_carry_over(self):
        """Tomasz is approved for the production database; that approves nothing for Marisol."""
        opened = hd.open_access_ticket(fresh(), ME, "production database admin")
        self.assertEqual(opened["status"], "awaiting_approval")

    def test_request_for_someone_else_is_refused_without_a_ticket(self):
        service = fresh()
        before = dict(service.tickets)
        for name in ("Tomasz Rell", "Tomasz", "someone who does not exist"):
            with self.subTest(name=name):
                opened = hd.open_access_ticket(service, ME, "viewer on finance reporting", for_employee=name)
                self.assertEqual((opened["status"], opened["reason"], opened["effects"]),
                                 ("blocked", "employee_unverified", 0))
                self.assertNotIn("Tomasz", json.dumps(opened))
        self.assertEqual(service.tickets, before)

    def test_self_references_are_the_session_employee(self):
        for name in (None, "me", "Marisol", "Marisol Quint"):
            with self.subTest(name=name):
                opened = hd.open_access_ticket(fresh(), ME, "viewer on finance reporting", for_employee=name)
                self.assertEqual(opened["status"], "ready_to_grant")

    def test_unverified_session_employee_is_blocked(self):
        opened = hd.open_access_ticket(fresh(), COLLEAGUE, "viewer on finance reporting")
        self.assertEqual((opened["status"], opened["reason"]), ("blocked", "employee_unverified"))
        self.assertEqual(hd.open_access_ticket(fresh(), None, "vpn")["reason"], "employee_unverified")

    def test_already_has_access_and_repeat_intake(self):
        service = fresh()
        self.assertEqual(hd.open_access_ticket(service, ME, "vpn")["status"], "already_has_access")
        first = hd.open_access_ticket(service, ME, "payroll admin")
        second = hd.open_access_ticket(service, ME, "payroll admin")
        self.assertEqual(first["ticket_ref"], second["ticket_ref"])
        self.assertEqual(first["approval_request_ref"], second["approval_request_ref"])


class GrantTests(unittest.TestCase):
    def test_grant_adds_exactly_the_approved_role(self):
        service = fresh()
        before = service.access(ME)
        opened = ready(service, "viewer on finance reporting")
        result = grant(service, opened["ticket_ref"])
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("succeeded", "verified_fixture_receipt", 1))
        self.assertEqual(result["scope"], {"role_ref": "FIN-REPORTS-VIEW", "system": "Orchard Finance Reporting",
                                           "level": "viewer", "access_expires": "2026-12-31"})
        self.assertEqual((result["unrelated_access_changed"], result["out_of_scope_changes"]), (0, 0))
        self.assertEqual(sorted(set(service.access(ME)) - set(before)), ["FIN-REPORTS-VIEW"])
        self.assertTrue(re.fullmatch(r"OW-CHG-\d{6}", result["change_ref"]))
        self.assertTrue(result["unresolved_work"])
        self.assertEqual(service.tickets[opened["ticket_ref"]]["status"], "completed")

    def test_only_the_confirmed_ticket(self):
        service = fresh()
        opened = ready(service, "viewer on finance reporting")
        result = hd.grant_access(service, ME, "IT-TKT-00000", opened["ticket_ref"])
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("blocked", "not_the_confirmed_ticket", 0))

    def test_unapproved_ticket_cannot_be_granted_even_when_confirmed(self):
        """The tool guard holds even if the engine's memory gate were bypassed."""
        service = fresh()
        opened = hd.open_access_ticket(service, ME, "payroll admin")
        before = service.access(ME)
        result = grant(service, opened["ticket_ref"])
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("blocked", "scope_unapproved", 0))
        self.assertEqual(service.access(ME), before)

    def test_ticket_of_another_employee_is_blocked(self):
        service = fresh()
        service.tickets["IT-TKT-11111"] = {"employee": COLLEAGUE, "role": "PROD-DB-ADMIN", "status": "ready_to_grant"}
        result = grant(service, "IT-TKT-11111")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "employee_unverified"))
        self.assertNotIn("PROD-DB-ADMIN", service.access(COLLEAGUE))

    def test_no_second_grant(self):
        service = fresh()
        opened = ready(service, "design library contributor")
        grant(service, opened["ticket_ref"])
        again = grant(service, opened["ticket_ref"])
        self.assertEqual((again["status"], again["effects"]), ("already_granted", 0))
        self.assertEqual(len(service.changes), 1)

    def test_lost_acknowledgement_reconciles_to_the_same_change(self):
        service = fresh()
        opened = ready(service, "analyst on the data warehouse")
        pending = grant(service, opened["ticket_ref"])
        self.assertEqual((pending["status"], pending["reason"], pending["effects"]),
                         ("pending", "ticket_action_unknown", 1))
        status = hd.check_ticket_status(service, ME, opened["ticket_ref"])
        self.assertEqual((status["status"], status["change_ref"], status["same_change"]),
                         ("completed", pending["change_ref"], True))
        self.assertEqual(len(service.changes), 1)

    def test_unavailable_directory_stays_pending_and_routes(self):
        service = fresh()
        opened = ready(service, "deployer on the build server")
        self.assertEqual(grant(service, opened["ticket_ref"])["status"], "pending")
        status = hd.check_ticket_status(service, ME, opened["ticket_ref"])
        self.assertEqual((status["status"], status["reconciled"]), ("unknown", False))
        routed = hd.route_access_owner(service, ME, opened["ticket_ref"], "directory cannot confirm")
        self.assertEqual((routed["status"], routed["routed_to"]), ("routed", "Engineering Productivity owner"))
        self.assertEqual(len(service.changes), 1)

    def test_case_metric_zero_out_of_scope_for_every_approved_role(self):
        """Access changes outside approved scope, divided by access requests, is 0 on the fixtures."""
        service = fresh()
        requests = changes_outside = 0
        for role_ref in list(service.roles):
            opened = hd.open_access_ticket(service, ME, role_ref)
            requests += 1
            if opened["status"] == "ready_to_grant":
                before = set(service.access(ME))
                result = grant(service, opened["ticket_ref"])
                added = set(service.access(ME)) - before
                changes_outside += result["out_of_scope_changes"] + len(added - {role_ref})
        self.assertEqual(changes_outside, 0)
        self.assertEqual(requests, len(service.roles))


class StatusAndRoutingTests(unittest.TestCase):
    def test_existing_ticket_awaits_the_owner(self):
        status = hd.check_ticket_status(fresh(), ME, "it-tkt-40117")
        self.assertEqual((status["status"], status["waiting_on"], status["access_changed"]),
                         ("awaiting_approval", "Finance Controls owner", False))

    def test_someone_elses_or_unknown_ticket(self):
        service = fresh()
        service.tickets["IT-TKT-22222"] = {"employee": COLLEAGUE, "role": "VPN-STANDARD", "status": "completed"}
        self.assertEqual(hd.check_ticket_status(service, ME, "IT-TKT-22222")["status"], "not_found")
        self.assertEqual(hd.check_ticket_status(service, ME, "IT-TKT-99999")["status"], "not_found")

    def test_identity_desk_changes_nothing(self):
        service = fresh()
        before = service.access(ME)
        routed = hd.route_identity_desk(service, ME, "forgot password")
        self.assertEqual((routed["status"], routed["access_changed"]), ("routed", False))
        self.assertTrue(routed["desk_ref"].startswith("OW-IDD-"))
        self.assertEqual(service.access(ME), before)


class SpecTests(unittest.TestCase):
    TOOLS = {"open_access_ticket", "grant_access", "check_ticket_status", "route_access_owner",
             "route_identity_desk", "load_session_employee", "*"}

    def test_conversation_spec_names_real_tools_and_kinds(self):
        spec = json.loads(SPEC.read_text())
        kinds = {c["kind"] for c in spec["conversations"]}
        self.assertEqual(kinds, {"normal", "adversarial", "recovery", "correction"})
        ids = [c["id"] for c in spec["conversations"]]
        self.assertEqual(len(ids), len(set(ids)))

        def walk(check):
            if check["type"] == "any_of":
                for inner in check["checks"]:
                    walk(inner)
            elif check["type"] == "tool_order":
                for step in check["steps"]:
                    self.assertIn(step["tool"], self.TOOLS)
            elif "tool" in check:
                self.assertIn(check["tool"], self.TOOLS)

        for conv in spec["conversations"]:
            for check in conv["checks"]:
                walk(check)


if __name__ == "__main__":
    unittest.main()
