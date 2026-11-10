"""Reuse an existing Strands tool; keep user input out of shared agent history."""
import json

class NetworkSession:
    def __init__(self, specialist):
        self.specialist = specialist
        self.area = None

    def select_area(self, area):
        if area not in {"north", "south"}:
            return {"status": "unknown_area"}
        if self.area is not None and self.area != area:
            return {"status": "area_changed"}
        self.area = area
        return {"status": "area_selected"}

    def inspect(self, question):
        if self.area is None:
            return {"status": "needs_area"}
        if not isinstance(question, str) or not question.strip() or len(question) > 1000:
            return {"status": "invalid_question"}
        # A fixed read-only tool, not a dispatcher accepting a model's tool name.
        result = self.specialist.tool.inspect_network(
            area=self.area, question=question, record_direct_tool_call=False
        )
        if result.get("status") != "success":
            return {"status": "network_evidence_unavailable"}
        try:
            content = result["content"]
            if len(content) != 1 or set(content[0]) != {"text"}:
                raise ValueError("content")
            observation = json.loads(content[0]["text"])
            if set(observation) != {"id", "area", "revision", "status", "advice"}:
                raise ValueError("observation")
            if observation["area"] != self.area or observation["status"] not in {"normal", "degraded"}:
                raise ValueError("scope")
            if not all(isinstance(v, str) and 0 < len(v) <= 1000 for v in observation.values()):
                raise ValueError("type")
            return {"status": "network_observation", "source": observation}
        except (ValueError, TypeError, KeyError):
            return {"status": "network_evidence_unavailable"}
