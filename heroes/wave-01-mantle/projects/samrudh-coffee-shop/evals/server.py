#!/usr/bin/env python3
"""
Universal Agent Evaluation Platform — Standalone Dashboard Server

Lightweight Python HTTP server supplying REST API endpoints for configuration management,
live Rasa port connectivity verification, real-time evaluation simulation execution,
stop control, and structured progress/log streaming for the Web UI.
"""

import os
import sys
import json
import time
import uuid
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Any, Optional

# Paths
EVAL_DIR = Path(__file__).resolve().parent
WEB_DIR = EVAL_DIR / "web"
CONFIG_FILE = EVAL_DIR / "eval_config.json"
OUTPUT_DIR = EVAL_DIR / "eval_results"
LOGS_DIR = OUTPUT_DIR / "logs"

WEB_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Load environment variables
for env_path in [EVAL_DIR / ".env", EVAL_DIR.parent / "coffee-shop" / ".env"]:
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

# Global Execution State
eval_state_lock = threading.Lock()
current_eval_state: Dict[str, Any] = {
    "is_running": False,
    "stop_requested": False,
    "current_scenario": "",
    "current_turn": 0,
    "completed_simulations": 0,
    "total_simulations": 0,
    "llm_calls_used": 0,
    "max_llm_calls_quota": 0,
    "logs": [],
    "summary": None,
    "detailed_results": []
}


def load_config() -> Dict[str, Any]:
    """Load configuration from eval_config.json."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "agent_title": "Universal Agent Evaluator",
        "rasa_host": "http://localhost",
        "rasa_port": 5005,
        "eval_model": "deepseek/deepseek-chat",
        "simulations_per_operation": 3,
        "max_turns_per_simulation": 5,
        "scenarios": {}
    }


def save_config(config_data: Dict[str, Any]):
    """Save configuration to eval_config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)


def check_rasa_status(host: str, port: int) -> Dict[str, Any]:
    """Check if Rasa API server is online and reachable."""
    url = f"{host}:{port}/version"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"online": True, "version": data.get("version", "unknown"), "url": f"{host}:{port}"}
    except Exception as e:
        return {"online": False, "error": str(e), "url": f"{host}:{port}"}


def log_to_state(msg: str, log_type: str = "system", sender: str = "System", details: Any = None):
    """Add timestamped structured log entry to live state log array."""
    t_str = time.strftime("%H:%M:%S")
    entry = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": t_str,
        "type": log_type,      # 'system', 'eval_agent', 'bot', 'tool', 'error', 'pass', 'fail'
        "sender": sender,
        "message": msg,
        "details": details,
        "formatted": f"[{t_str}] [{log_type.upper()}] {sender}: {msg}"
    }
    with eval_state_lock:
        current_eval_state["logs"].append(entry)


def call_llm(messages: List[Dict[str, str]], system_prompt: str = "", temperature: float = 0.3) -> str:
    """Invoke LLM API using OpenRouter (or OpenAI/Gemini fallback)."""
    with eval_state_lock:
        current_eval_state["llm_calls_used"] += 1

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    eval_model = current_eval_state.get("eval_model", "deepseek/deepseek-chat")

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    # 1. OpenRouter API
    if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/samrudh/rasa-agent-eval",
            "X-Title": "Rasa Agent Eval Harness"
        }
        payload = {"model": eval_model, "messages": full_messages, "temperature": temperature}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log_to_state(f"OpenRouter API call error: {e}", log_type="error", sender="LLM Provider")

    # 2. OpenAI API fallback
    if openai_key and openai_key != "your_openai_api_key_here":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
        payload = {"model": "gpt-4o-mini", "messages": full_messages, "temperature": temperature}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log_to_state(f"OpenAI API call error: {e}", log_type="error", sender="LLM Provider")

    # 3. Gemini API fallback
    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        headers = {"Content-Type": "application/json"}
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {"contents": contents, "generationConfig": {"temperature": temperature}}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            return f"[LLM Error: {e}]"

    return "[Error: No valid LLM API key provided]"


def fetch_rasa_tracker_logs(rasa_url: str, sender_id: str) -> Dict[str, Any]:
    """Query Rasa REST API tracker endpoint to fetch skills, tools, and full event log."""
    url = f"{rasa_url}/conversations/{sender_id}/tracker"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            events = data.get("events", [])
            skills = []
            tools = []
            logs = []
            for ev in events:
                et = ev.get("event")
                if et == "user": logs.append(f"USER: {ev.get('text')}")
                elif et == "bot": logs.append(f"BOT: {ev.get('text')}")
                elif et == "skill_activated":
                    sname = ev.get("name")
                    if sname:
                        skills.append(str(sname))
                elif et == "tool_executed" or et == "action":
                    aname = ev.get("name")
                    if aname and aname not in ("action_listen", "action_session_start"):
                        tools.append(str(aname))
            return {
                "skills_activated": [str(s) for s in list(set(skills)) if s is not None],
                "tools_executed": [str(t) for t in list(set(tools)) if t is not None],
                "transcript": "\n".join(logs)
            }
    except Exception as e:
        return {"skills_activated": [], "tools_executed": [], "transcript": ""}


def execute_evaluation_thread(params: Dict[str, Any]):
    """Background worker thread executing full multi-turn evaluation simulations."""
    try:
        config = load_config()
        rasa_host = params.get('rasa_host', config.get('rasa_host', 'http://localhost'))
        rasa_port = int(params.get('rasa_port', config.get('rasa_port', 5005)))
        rasa_url = f"{rasa_host}:{rasa_port}"
        simulations_per_op = int(params.get("simulations_per_operation", config.get("simulations_per_operation", 3)))
        max_turns = int(params.get("max_turns_per_simulation", config.get("max_turns_per_simulation", 5)))
        eval_model = params.get("eval_model", config.get("eval_model", "deepseek/deepseek-chat"))
        selected_keys = params.get("selected_scenarios", None)

        all_scenarios = config.get("scenarios", {})
        if selected_keys and isinstance(selected_keys, list):
            enabled_scenarios = {k: v for k, v in all_scenarios.items() if k in selected_keys}
        else:
            enabled_scenarios = {k: v for k, v in all_scenarios.items() if v.get("enabled", True)}

        ops_count = len(enabled_scenarios)
        total_sims = ops_count * simulations_per_op
        max_llm_quota = total_sims * (max_turns + 1)

        with eval_state_lock:
            current_eval_state.update({
                "is_running": True,
                "stop_requested": False,
                "eval_model": eval_model,
                "current_scenario": "Initializing...",
                "current_turn": 0,
                "completed_simulations": 0,
                "total_simulations": total_sims,
                "llm_calls_used": 0,
                "max_llm_calls_quota": max_llm_quota,
                "logs": [],
                "summary": None,
                "detailed_results": []
            })

        log_to_state(f"🚀 Starting Evaluation Suite: {ops_count} Active Scenarios x {simulations_per_op} Runs = {total_sims} Simulations", log_type="system", sender="System")
        log_to_state(f"Target Rasa Server: {rasa_url} | Eval Model: {eval_model}", log_type="system", sender="System")

        # Check Rasa status prior to launching
        st = check_rasa_status(rasa_host, rasa_port)
        if not st["online"]:
            log_to_state(f"❌ Connection Failed: Target Rasa Agent on {rasa_url} is offline or unreachable!", log_type="error", sender="Rasa Client")
            log_to_state(f"Please ensure your Rasa server is running (e.g., 'make run' on port {rasa_port}) before starting the evaluation.", log_type="error", sender="System")
            with eval_state_lock:
                current_eval_state["is_running"] = False
                current_eval_state["current_scenario"] = "Stopped (Rasa Offline)"
            return

        detailed_results = []
        summary_by_op = {}

        for op_key, scenario in enabled_scenarios.items():
            with eval_state_lock:
                if current_eval_state["stop_requested"]:
                    break

            log_to_state(f"▶ Starting Scenario: {scenario.get('title', op_key)}", log_type="system", sender="System")
            op_runs = []

            for sim_i in range(1, simulations_per_op + 1):
                with eval_state_lock:
                    if current_eval_state["stop_requested"]:
                        break

                session_id = f"sim-{op_key}-{sim_i}-{uuid.uuid4().hex[:6]}"
                with eval_state_lock:
                    current_eval_state["current_scenario"] = scenario.get("title", op_key)
                    current_eval_state["current_turn"] = 1

                log_to_state(f"➜ Run #{sim_i}/{simulations_per_op} ({session_id}) initiated", log_type="system", sender="System")

                user_msg = scenario.get("initial_user_message", "Hello")
                transcript = []
                sim_messages = [{"role": "user", "content": f"The conversation starts. First message: '{user_msg}'"}]

                turn_count = 0
                for turn in range(max_turns):
                    with eval_state_lock:
                        if current_eval_state["stop_requested"]:
                            break

                    turn_count += 1
                    with eval_state_lock:
                        current_eval_state["current_turn"] = turn_count

                    # 1. Log Eval Agent turn
                    log_to_state(user_msg, log_type="eval_agent", sender="Eval Agent (Simulator)")
                    transcript.append({"role": "user", "content": user_msg})

                    # 2. Send to Rasa REST API
                    headers = {"Content-Type": "application/json"}
                    payload = {"sender": session_id, "message": user_msg}
                    bot_responses = []
                    has_error = False

                    try:
                        req = urllib.request.Request(f"{rasa_url}/webhooks/rest/webhook", data=json.dumps(payload).encode("utf-8"), headers=headers)
                        with urllib.request.urlopen(req, timeout=45) as resp:
                            res_data = json.loads(resp.read().decode("utf-8"))
                            for item in res_data:
                                if "text" in item and item["text"]:
                                    bot_responses.append(item["text"].strip())
                    except Exception as e:
                        has_error = True
                        err_text = f"Connection error to Rasa webhook ({e})"
                        log_to_state(err_text, log_type="error", sender="Rasa Client")
                        transcript.append({"role": "bot", "content": f"[Error: {err_text}]"})
                        break

                    bot_combined = "\n".join(bot_responses) if bot_responses else "[No Response]"
                    if not has_error:
                        log_to_state(bot_combined, log_type="bot", sender="Target Rasa Bot")
                        transcript.append({"role": "bot", "content": bot_combined})

                    # 3. Generate Next User Simulator Turn
                    sim_prompt = (
                        f"{scenario.get('system_prompt', '')}\n"
                        "If your goal is completely achieved and confirmed, say: 'THANK YOU, GOT IT'. Otherwise, generate the next realistic user message."
                    )
                    sim_messages.append({"role": "assistant", "content": user_msg})
                    sim_messages.append({"role": "user", "content": f"BOT Response: {bot_combined}\nNext user turn:"})

                    next_user_msg = call_llm(sim_messages[-4:], system_prompt=sim_prompt, temperature=0.4)
                    
                    if any(kw in next_user_msg.upper() for kw in ("THANK YOU, GOT IT", "ORDER CONFIRMED", "THAT IS ALL", "GOT IT, THANKS")):
                        log_to_state(next_user_msg, log_type="eval_agent", sender="Eval Agent (Simulator)")
                        transcript.append({"role": "user", "content": next_user_msg})
                        break

                    user_msg = next_user_msg

                # Fetch Tracker Events & Execute LLM Judge
                engine_logs = fetch_rasa_tracker_logs(rasa_url, session_id)
                tools_list = [str(t) for t in engine_logs.get("tools_executed", []) if t]
                if tools_list:
                    log_to_state(f"Tools Executed: {', '.join(tools_list)}", log_type="tool", sender="Rasa Engine")

                skills_list = [str(s) for s in engine_logs.get("skills_activated", []) if s]
                if skills_list:
                    log_to_state(f"Skills Activated: {', '.join(skills_list)}", log_type="tool", sender="Rasa Engine")

                judge_prompt = (
                    f"Scenario: {scenario.get('title', op_key)}\n"
                    f"Expected Criteria: {scenario.get('success_criteria', '')}\n"
                    "Review dialogue transcript. Return JSON strictly in format:\n"
                    "{\"task_completed\": true|false, \"score\": 1.0|0.0, \"summary\": \"Brief justification\"}"
                )
                transcript_str = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in transcript])
                judge_res_str = call_llm([{"role": "user", "content": f"Transcript:\n{transcript_str}"}], system_prompt=judge_prompt, temperature=0.1)

                try:
                    c_json = judge_res_str.split("```")[1] if "```" in judge_res_str else judge_res_str
                    if c_json.startswith("json"): c_json = c_json[4:]
                    j_res = json.loads(c_json.strip())
                except Exception:
                    is_pass = "true" in judge_res_str.lower()
                    j_res = {"task_completed": is_pass, "score": 1.0 if is_pass else 0.0, "summary": judge_res_str[:150]}

                passed = j_res.get("task_completed", False)
                run_record = {
                    "simulation_id": session_id,
                    "scenario_key": op_key,
                    "title": scenario.get("title", op_key),
                    "run_index": sim_i,
                    "turns_taken": turn_count,
                    "passed": passed,
                    "score": j_res.get("score", 1.0 if passed else 0.0),
                    "summary": j_res.get("summary", ""),
                    "skills_activated": engine_logs["skills_activated"],
                    "tools_executed": engine_logs["tools_executed"],
                    "transcript": transcript
                }
                op_runs.append(run_record)
                detailed_results.append(run_record)

                if passed:
                    log_to_state(f"✅ Run #{sim_i} PASS — {run_record['summary']}", log_type="pass", sender="LLM Judge")
                else:
                    log_to_state(f"❌ Run #{sim_i} FAIL — {run_record['summary']}", log_type="fail", sender="LLM Judge")

                with eval_state_lock:
                    current_eval_state["completed_simulations"] += 1
                    current_eval_state["detailed_results"] = detailed_results

            passed_c = sum(1 for r in op_runs if r["passed"])
            summary_by_op[op_key] = {
                "title": scenario.get("title", op_key),
                "total_runs": len(op_runs),
                "passed_runs": passed_c,
                "pass_rate_pct": (passed_c / len(op_runs)) * 100.0 if op_runs else 0.0
            }

        total_passed = sum(1 for r in detailed_results if r["passed"])
        actual_total_sims = len(detailed_results)
        overall_pass_rate = (total_passed / actual_total_sims) * 100.0 if actual_total_sims > 0 else 0.0

        summary_final = {
            "overall_pass_rate_pct": overall_pass_rate,
            "total_simulations": actual_total_sims,
            "total_passed": total_passed,
            "llm_calls_used": current_eval_state["llm_calls_used"],
            "max_llm_quota": max_llm_quota,
            "summary_by_operation": summary_by_op
        }

        with eval_state_lock:
            current_eval_state["is_running"] = False
            current_eval_state["current_scenario"] = "Completed" if not current_eval_state["stop_requested"] else "Stopped"
            current_eval_state["summary"] = summary_final

        status_msg = "Evaluation Stopped by User" if current_eval_state["stop_requested"] else f"🎉 Evaluation Complete! Pass Rate: {overall_pass_rate:.1f}% ({total_passed}/{actual_total_sims})"
        log_to_state(status_msg, log_type="system", sender="System")

        # Export report to JSON
        with open(OUTPUT_DIR / "simulation_report.json", "w") as f:
            json.dump({"summary": summary_final, "detailed_runs": detailed_results}, f, indent=2)

    except Exception as e:
        log_to_state(f"❌ Worker thread exception: {e}", log_type="error", sender="System")
        with eval_state_lock:
            current_eval_state["is_running"] = False
            current_eval_state["current_scenario"] = "Error"


# ==============================================================================
# HTTP Request Handler
# ==============================================================================

class DashboardHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Serve static UI files from web/ and handle /api/ REST endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_json(self, data: Dict[str, Any], status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/config":
            self._send_json(load_config())
        elif path == "/api/status":
            config = load_config()
            host = config.get("rasa_host", "http://localhost")
            port = config.get("rasa_port", 5005)
            self._send_json(check_rasa_status(host, port))
        elif path == "/api/eval/progress":
            with eval_state_lock:
                self._send_json(current_eval_state)
        else:
            super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        params = json.loads(body) if body else {}

        if path == "/api/config":
            save_config(params)
            self._send_json({"status": "saved", "config": params})
        elif path == "/api/eval/start":
            with eval_state_lock:
                if current_eval_state["is_running"]:
                    self._send_json({"error": "Evaluation simulation is already running!"}, status=400)
                    return

            t = threading.Thread(target=execute_evaluation_thread, args=(params,))
            t.daemon = True
            t.start()
            self._send_json({"status": "started", "message": "Evaluation simulation started in background."})
        elif path == "/api/eval/stop":
            with eval_state_lock:
                if current_eval_state["is_running"]:
                    current_eval_state["stop_requested"] = True
                    self._send_json({"status": "stopping", "message": "Stop request submitted."})
                else:
                    self._send_json({"status": "idle", "message": "No simulation currently running."})
        else:
            self._send_json({"error": "Endpoint not found"}, status=404)


def main():
    port = 8080
    server_address = ("", port)
    httpd = HTTPServer(server_address, DashboardHTTPRequestHandler)
    print("=" * 80)
    print(f" 🤖 Universal Agent Evaluation Platform — Server Running")
    print(f" 🌐 Dashboard URL : http://localhost:{port}")
    print(f" ⚙️ Config File   : {CONFIG_FILE}")
    print("=" * 80)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Dashboard Server.")
        httpd.server_close()

if __name__ == "__main__":
    main()
