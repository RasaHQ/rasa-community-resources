"""Protected contract-level acceptance for the zeocore widget types (owner: the specification owner). Offline, no key, no network.

Run with a Python 3.12 interpreter that has the pinned zeocore wheel installed:  python accept_contract.py
It grades the shared contract only (scenarios S2, S3, S5, S7, M1 and the closed registry); the product has its own scenarios.
"""
import unittest

import zeo_core.contracts.ui.widgets as w

NOW = "2026-10-22T10:00:00Z"


def flight(**over):
    payload = {"flight_number": "DEMO101", "route": {"from": "LHR", "to": "JFK"},
               "scheduled_departure": "2026-10-22T10:00:00Z", "estimated_departure": None,
               "scheduled_arrival": "2026-10-22T17:00:00Z", "estimated_arrival": None,
               "terminal": None, "reported_status": "Scheduled", "source_timestamp": None}
    return {"id": "d-flight", "source": "replay-fixture", "fetched_at": NOW, "as_of": None, "replay": True,
            "delayed": None, "assumptions": [], "payload": {**payload, **over}, "error": None}


def weather(ident="d-wx"):
    hours = [{"time": "2026-10-22T17:00:00Z", "temp_c": 17.0, "precip_prob": 20.0, "precip_mm": 0.0}]
    payload = {"location": "New York", "timezone": "UTC", "valid_from": "2026-10-22T17:00:00Z",
               "valid_to": "2026-10-22T18:00:00Z", "hourly": hours, "arrival_hour": "2026-10-22T17:00:00Z"}
    return {"id": ident, "source": "replay-fixture", "fetched_at": NOW, "as_of": None, "replay": True,
            "delayed": None, "assumptions": [], "payload": payload, "error": None}


def market(delayed_flag, payload_delayed=True):
    payload = {"symbols": [{"symbol": "AAA", "price": 10.0, "change": 0.5, "change_pct": 5.0}],
               "market_status": "closed", "quote_time": "2026-10-21T20:00:00Z", "delayed": payload_delayed,
               "series": {"AAA": [{"time": "2026-10-21T19:00:00Z", "value": 9.5}]}}
    return {"id": "d-mkt", "source": "replay-fixture", "fetched_at": NOW, "as_of": None, "replay": True,
            "delayed": delayed_flag, "assumptions": [], "payload": payload, "error": None}


def timeline(assumptions, kind="assumption"):
    payload = {"steps": [{"label": "Arrival", "time": "2026-10-22T17:00:00Z"}],
               "transfer_minutes": {"value": 90, "kind": kind}, "meeting_time": "2026-10-22T21:00:00Z",
               "margin_minutes": 150.0}
    return {"id": "d-tl", "source": "replay-fixture", "fetched_at": NOW, "as_of": None, "replay": True,
            "delayed": None, "assumptions": assumptions, "payload": payload, "error": None}


def event(request_id, widget_id, component, data_ref, revision):
    return w.WidgetUpsert(type="widget.upsert", request_id=request_id, widget_id=widget_id,
                          component=component, data_ref=data_ref, revision=revision)


class Contract(unittest.TestCase):
    def test_registry_holds_exactly_the_four_components(self):
        self.assertEqual(sorted(w.COMPONENTS), ["arrival_timeline", "flight_status", "market_watchlist", "weather_hourly"])

    def test_an_event_with_an_extra_key_is_rejected(self):
        with self.assertRaises(Exception):
            w.WidgetUpsert(type="widget.upsert", request_id="r1", widget_id="a", component="flight_status",
                           data_ref="d", revision=1, extra="x")

    def test_s2_an_equal_or_lower_revision_is_ignored(self):
        board = w.WidgetBoard(); board.begin_request("r1")
        ref = w.DataRef.model_validate(flight())
        self.assertTrue(board.apply(event("r1", "flight", "flight_status", "d-flight", 2), ref))
        self.assertFalse(board.apply(event("r1", "flight", "flight_status", "d-flight", 2), ref))
        self.assertFalse(board.apply(event("r1", "flight", "flight_status", "d-flight", 1), ref))
        self.assertEqual(len(board.cards()), 1)

    def test_s5_a_late_result_for_a_superseded_request_cannot_overwrite(self):
        board = w.WidgetBoard(); board.begin_request("r-london")
        board.begin_request("r-paris")
        board.apply(event("r-paris", "weather", "weather_hourly", "d-paris", 1), w.DataRef.model_validate(weather("d-paris")))
        with self.assertRaises(w.WidgetRefused):
            board.apply(event("r-london", "weather", "weather_hourly", "d-london", 5), w.DataRef.model_validate(weather("d-london")))
        self.assertEqual(board.cards()["weather"].id, "d-paris")

    def test_s5b_changing_one_card_does_not_wipe_the_other_cards(self):
        """The organiser's follow-up 'show tomorrow morning instead' changes weather only; the flight card must stay."""
        board = w.WidgetBoard(); board.begin_request("r1")
        board.apply(event("r1", "flight", "flight_status", "d-flight", 1), w.DataRef.model_validate(flight()))
        board.apply(event("r1", "weather", "weather_hourly", "d-wx", 1), w.DataRef.model_validate(weather()))
        board.begin_request("r2", replaces=["weather"])
        board.apply(event("r2", "weather", "weather_hourly", "d-wx2", 1), w.DataRef.model_validate(weather("d-wx2")))
        self.assertIn("flight", board.cards(), "a follow-up request removed an unrelated card")
        self.assertEqual(board.cards()["weather"].id, "d-wx2")

    def test_s5c_the_replaced_widgets_old_request_cannot_overwrite_the_new_card(self):
        board = w.WidgetBoard(); board.begin_request("r1")
        board.apply(event("r1", "weather", "weather_hourly", "d-wx", 1), w.DataRef.model_validate(weather()))
        board.begin_request("r2", replaces=["weather"])
        board.apply(event("r2", "weather", "weather_hourly", "d-wx2", 1), w.DataRef.model_validate(weather("d-wx2")))
        with self.assertRaises(w.WidgetRefused):
            board.apply(event("r1", "weather", "weather_hourly", "d-wx3", 9), w.DataRef.model_validate(weather("d-wx3")))
        self.assertEqual(board.cards()["weather"].id, "d-wx2")

    def test_s5d_the_old_request_may_still_update_a_widget_it_kept(self):
        board = w.WidgetBoard(); board.begin_request("r1")
        board.apply(event("r1", "flight", "flight_status", "d-flight", 1), w.DataRef.model_validate(flight()))
        board.begin_request("r2", replaces=["weather"])
        refreshed = flight(); refreshed["id"] = "d-flight2"
        self.assertTrue(board.apply(event("r1", "flight", "flight_status", "d-flight2", 2), w.DataRef.model_validate(refreshed)))

    def test_s3_provider_time_is_nullable_and_is_not_filled_from_fetch_time(self):
        ref = w.DataRef.model_validate(flight())
        self.assertIsNone(ref.as_of)
        self.assertNotEqual(ref.as_of, ref.fetched_at)

    def test_s3_a_data_ref_with_no_as_of_key_is_refused(self):
        data = flight(); del data["as_of"]
        with self.assertRaises(Exception):
            w.DataRef.model_validate(data)

    def test_m1_delayed_market_data_must_say_delayed_in_the_data_ref(self):
        w.DataRef.model_validate(market(True)).check("market_watchlist")
        with self.assertRaises(Exception):
            w.DataRef.model_validate(market(None)).check("market_watchlist")
        with self.assertRaises(Exception):
            w.DataRef.model_validate(market(False)).check("market_watchlist")

    def test_s7_a_transfer_time_must_be_a_listed_assumption(self):
        listed = [{"label": "transfer_minutes", "value": 90, "kind": "assumption"}]
        w.DataRef.model_validate(timeline(listed)).check("arrival_timeline")
        with self.assertRaises(Exception):
            w.DataRef.model_validate(timeline([])).check("arrival_timeline")
        with self.assertRaises(Exception):
            w.DataRef.model_validate(timeline(listed, kind="traffic")).check("arrival_timeline")

    def test_a_failed_source_carries_an_error_and_no_payload(self):
        data = flight(); data["error"] = {"reason": "provider_unavailable"}
        with self.assertRaises(w.WidgetRefused):
            w.DataRef.model_validate(data).check("flight_status")
        data["payload"] = {}
        w.DataRef.model_validate(data).check("flight_status")


class PayloadShapes(unittest.TestCase):
    """MC120-F1: the JSON schemas are envelope-only; these fixtures pin the authoritative per-component payload validation."""

    def _refused(self, data, component):
        with self.assertRaises(Exception):
            w.DataRef.model_validate(data).check(component)

    def test_f1_a_flight_payload_cannot_be_checked_as_a_weather_card(self):
        self._refused(flight(), "weather_hourly")

    def test_f1_a_weather_payload_cannot_be_checked_as_a_flight_card(self):
        self._refused(weather(), "flight_status")

    def test_f1_an_arbitrary_object_is_not_a_payload_for_any_component(self):
        for component in w.COMPONENTS:
            data = flight(); data["payload"] = {"anything": 1}
            self._refused(data, component)

    def test_f1_a_missing_required_field_is_refused(self):
        data = flight(); del data["payload"]["scheduled_arrival"]
        self._refused(data, "flight_status")

    def test_f1_an_extra_payload_field_is_refused(self):
        data = flight(); data["payload"]["html"] = "x"
        self._refused(data, "flight_status")

    def test_f1_markup_and_control_characters_in_values_are_refused(self):
        for bad in ("<script>alert(1)</script>", "a<b", "a>b", "x\x00y"):
            data = flight(reported_status=bad)
            self._refused(data, "flight_status")

    def test_f1_known_gap_urls_pass_the_contract_and_are_refused_by_the_product_adapter(self):
        """Documented gap, not a pass: dev17's Text type refuses markup but not URLs or 'javascript:'.
        The product's briefing/data.py text() refuses '://' at the adapter. If a later wheel refuses URLs, this test fails
        and must be inverted."""
        for url in ("see https://example.com/x", "javascript:alert(1)"):
            w.DataRef.model_validate(flight(reported_status=url)).check("flight_status")

    def test_f1_each_component_has_one_valid_example_that_passes(self):
        w.DataRef.model_validate(flight()).check("flight_status")
        w.DataRef.model_validate(weather()).check("weather_hourly")
        w.DataRef.model_validate(market(True)).check("market_watchlist")
        w.DataRef.model_validate(timeline([{"label": "transfer_minutes", "value": 90, "kind": "assumption"}])).check("arrival_timeline")


if __name__ == "__main__":
    unittest.main()
