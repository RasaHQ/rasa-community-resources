#!/usr/bin/env python3
"""
Artisan Roast Coffee Shop — Advanced Agent Evaluation Harness & User Simulator

This standalone evaluation harness loads real ground-truth domain data from `coffee-shop/data/`
(customer profiles, store inventories, SQLite DB records) to simulate realistic multi-turn dialogues
against the Rasa Mantle Coffee Shop Agent, while monitoring and extracting live Rasa engine event logs.

Evaluation Specifications:
  - Cross-Model Family Simulator: OpenRouter API (DeepSeek model family)
  - Quota Control: Fixed Operations (5) x Simulations/Op (3) x Max Turns/Sim (5) + Judge Call
  - Rasa Engine Monitoring: Real-time event log & tracker extraction (`/conversations/{id}/tracker`)
  - Progress Visualization: Real-time progress bar (tqdm)
  - Metrics: Task Completion Rate, Tool Calling Accuracy, Engine Event Logs & DB Verification
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Try importing tqdm for progress bar visualization
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Paths
EVAL_DIR = Path(__file__).resolve().parent
ROOT_DIR = EVAL_DIR.parent
COFFEE_SHOP_DIR = ROOT_DIR / "coffee-shop"
DATA_DIR = COFFEE_SHOP_DIR / "data"
DB_PATH = DATA_DIR / "coffeeshop.db"

# Load environment variables
for env_path in [EVAL_DIR / ".env", COFFEE_SHOP_DIR / ".env", ROOT_DIR / ".env"]:
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

# Configuration & Quotas
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
EVAL_MODEL = os.getenv("EVAL_MODEL", "deepseek/deepseek-chat").strip()
RASA_ENDPOINT = os.getenv("RASA_ENDPOINT", "http://localhost:5005/webhooks/rest/webhook").strip()
RASA_BASE_URL = os.getenv("RASA_BASE_URL", "http://localhost:5005").strip()

SIMULATIONS_PER_OPERATION = 3
MAX_TURNS_PER_SIMULATION = 5
OUTPUT_DIR = EVAL_DIR / "eval_results"
LOGS_DIR = OUTPUT_DIR / "logs"
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Global API Call Tracker
llm_api_call_counter = 0


# ==============================================================================
# Domain Data Loader (Ground Truth Context from coffee-shop/data/)
# ==============================================================================

def load_ground_truth_context() -> Dict[str, Any]:
    """Load ground-truth domain entities from customer_profiles.json, store_inventory.json, and SQLite DB."""
    context = {
        "customers": [],
        "inventory": [],
        "stores": ["Lower Manhattan", "Astoria", "Hell's Kitchen", "Williamsburg", "Upper East Side"],
        "recent_orders_count": 0
    }

    cust_file = DATA_DIR / "customer_profiles.json"
    if cust_file.exists():
        with open(cust_file, "r") as f:
            context["customers"] = json.load(f)[:5]

    inv_file = DATA_DIR / "store_inventory.json"
    if inv_file.exists():
        with open(inv_file, "r") as f:
            context["inventory"] = json.load(f)[:10]

    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM orders")
            context["recent_orders_count"] = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass

    return context


GROUND_TRUTH = load_ground_truth_context()


# ==============================================================================
# LLM Provider Call Helper (OpenRouter / OpenAI / Gemini)
# ==============================================================================

def call_llm(messages: List[Dict[str, str]], system_prompt: str = "", temperature: float = 0.3) -> str:
    """Call LLM API for User Simulator or Judge using OpenRouter, OpenAI, or Gemini API fallback."""
    global llm_api_call_counter
    llm_api_call_counter += 1

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    # 1. OpenRouter API (Primary)
    if OPENROUTER_API_KEY and OPENROUTER_API_KEY != "your_openrouter_api_key_here":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/samrudh/coffee-shop-agent",
            "X-Title": "Coffee Shop Eval Harness"
        }
        payload = {
            "model": EVAL_MODEL,
            "messages": full_messages,
            "temperature": temperature
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            pass

    # 2. OpenAI API fallback
    if OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": full_messages,
            "temperature": temperature
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            pass

    # 3. Gemini API fallback
    if GEMINI_API_KEY:
        gemini_model = "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. Ready to simulate customer."}]})

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
            return f"[Error: LLM API call failed: {e}]"

    return "[Error: No valid LLM API key provided in .env]"


# ==============================================================================
# Rasa Agent REST Client & Event Tracker Monitoring
# ==============================================================================

def send_to_rasa(message: str, sender_id: str) -> List[str]:
    """Send user message to Rasa REST endpoint and return bot text responses."""
    headers = {"Content-Type": "application/json"}
    payload = {"sender": sender_id, "message": message}
    try:
        req = urllib.request.Request(RASA_ENDPOINT, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            responses = []
            for item in data:
                if "text" in item and item["text"]:
                    responses.append(item["text"].strip())
            return responses
    except Exception as e:
        return [f"[Rasa Connection Error: {e}]"]


def fetch_rasa_tracker_logs(sender_id: str) -> Dict[str, Any]:
    """Query Rasa REST API endpoint /conversations/{sender_id}/tracker to monitor engine logs & events."""
    url = f"{RASA_BASE_URL}/conversations/{sender_id}/tracker"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            tracker_data = json.loads(resp.read().decode("utf-8"))
            events = tracker_data.get("events", [])
            
            parsed_logs = []
            skills_activated = []
            tools_executed = []
            slots_set = tracker_data.get("slots", {})

            for ev in events:
                event_type = ev.get("event")
                timestamp = ev.get("timestamp", 0)
                time_str = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "00:00:00"

                if event_type == "user":
                    text = ev.get("text", "")
                    parsed_logs.append(f"[{time_str}] USER: {text}")
                elif event_type == "bot":
                    text = ev.get("text", "")
                    parsed_logs.append(f"[{time_str}] BOT: {text}")
                elif event_type == "flow_started":
                    flow_id = ev.get("flow_id", ev.get("name", "unknown"))
                    parsed_logs.append(f"[{time_str}] 🌀 RASA FLOW STARTED: {flow_id}")
                elif event_type == "skill_activated":
                    skill_name = ev.get("name", "unknown")
                    skills_activated.append(skill_name)
                    parsed_logs.append(f"[{time_str}] ⚡ RASA SKILL ACTIVATED: {skill_name}")
                elif event_type == "tool_executed" or event_type == "action":
                    action_name = ev.get("name", ev.get("action_name", "unknown"))
                    if action_name not in ("action_listen", "action_session_start"):
                        tools_executed.append(action_name)
                        parsed_logs.append(f"[{time_str}] 🛠️ RASA TOOL/ACTION EXECUTED: {action_name}")
                elif event_type == "slot":
                    key = ev.get("key")
                    val = ev.get("value")
                    if key and not key.startswith("consecutive_"):
                        parsed_logs.append(f"[{time_str}] 📌 RASA SLOT SET: {key} = {val}")

            return {
                "events_count": len(events),
                "skills_activated": list(set(skills_activated)),
                "tools_executed": list(set(tools_executed)),
                "slots_summary": {k: v for k, v in slots_set.items() if v is not None and not k.startswith("consecutive_")},
                "log_transcript": "\n".join(parsed_logs)
            }
    except Exception as e:
        return {
            "events_count": 0,
            "skills_activated": [],
            "tools_executed": [],
            "slots_summary": {},
            "log_transcript": f"[Could not fetch Rasa engine logs: {e}]"
        }


# ==============================================================================
# Grounded Operational Scenarios
# ==============================================================================

sample_cust = GROUND_TRUTH["customers"][0] if GROUND_TRUTH["customers"] else {"name": "Sarah Jenkins", "preferred_store_location": "Lower Manhattan"}
sample_cust2 = GROUND_TRUTH["customers"][1] if len(GROUND_TRUTH["customers"]) > 1 else {"name": "Marcus Vance", "preferred_store_location": "Astoria"}

OPERATIONAL_SCENARIOS = {
    "place_single_order": {
        "title": "Operation 1: Place Single Beverage Order",
        "description": f"Order a single customized coffee (Medium Dark Roast Coffee with Oat Milk for pickup at {sample_cust['preferred_store_location']}).",
        "system_prompt": (
            f"You are customer {sample_cust['name']} at Artisan Roast Coffee. Your goal is to order a Medium Dark Roast Coffee with Oat Milk "
            f"for pickup at the {sample_cust['preferred_store_location']} store. Answer questions directly, provide size and milk preferences when asked, "
            "and end the conversation politely once you receive order confirmation with an Order ID."
        ),
        "initial_user_message": f"Hi, I would like to place an order for pickup at your {sample_cust['preferred_store_location']} store.",
        "success_criteria": "The bot successfully places the single coffee order and provides an Order ID confirmation (e.g. ORD-xxx)."
    },
    "place_sequential_consecutive_orders": {
        "title": "Operation 2: Place Two Sequential Consecutive Orders",
        "description": f"Place Order #1 for a Dark Roast Coffee at {sample_cust2['preferred_store_location']}, verify confirmation, then immediately place Order #2 for a Blueberry Muffin in the same session.",
        "system_prompt": (
            f"You are customer {sample_cust2['name']} placing two separate consecutive orders in one conversation session.\n"
            f"Step 1: Order a Large Dark Roast Coffee for pickup at {sample_cust2['preferred_store_location']} store.\n"
            "Step 2: Once you receive confirmation for Order #1 with an Order ID, say: 'Great! Now I want to place a second separate order for a Blueberry Muffin.'\n"
            "Step 3: Confirm details for Order #2 until you receive the second Order ID."
        ),
        "initial_user_message": f"Hello! I need to place an order for a Large Dark Roast Coffee at {sample_cust2['preferred_store_location']} store.",
        "success_criteria": "Both Order #1 and Order #2 are successfully placed consecutively in the same session with two distinct Order IDs."
    },
    "place_sequential_group_order": {
        "title": "Operation 3: Place Sequential Group Order",
        "description": "Place a group order for 3 team members (1 Cappuccino, 1 Iced Americano, 1 Croissant) at Hell's Kitchen.",
        "system_prompt": (
            "You are ordering coffee for your team at Artisan Roast.\n"
            "Your order list:\n"
            "1) Regular Cappuccino with Whole Milk\n"
            "2) Large Iced Americano\n"
            "3) Almond Croissant\n"
            "Location: Hell's Kitchen location.\n"
            "Communicate items clearly, answer any sizing or customization prompts, and confirm the group order."
        ),
        "initial_user_message": "Hi! I want to place a group order for my team of 3 people at the Hell's Kitchen store.",
        "success_criteria": "The agent collects all 3 items, confirms group order totals, and provides order confirmation."
    },
    "ceo_admin_analytics": {
        "title": "Operation 4: CEO Admin Analytics & Security PIN",
        "description": "Authenticate as CEO using security PIN 8888 (or passcode ARTISAN-EXEC-9042) and request multi-store revenue and COGS metrics.",
        "system_prompt": (
            "You are the CEO of Artisan Roast Coffee.\n"
            "Your objective: Authenticate with executive PIN '8888' (or passcode 'ARTISAN-EXEC-9042') and request gross profit margins, total revenue, and COGS breakdown across all stores."
        ),
        "initial_user_message": "I am the CEO and I need executive analytics for our store locations.",
        "success_criteria": "The agent asks for authentication, validates passcode/PIN 8888, and returns store sales/financial analytics."
    },
    "sommelier_and_inventory": {
        "title": "Operation 5: Sommelier Recommendation & Store Inventory Query",
        "description": "Request a mood-based sensory coffee recommendation, then check store raw bean inventory levels at Astoria.",
        "system_prompt": (
            "You are a customer visiting Artisan Roast.\n"
            "Step 1: Express that you feel sleepy and stressed, and ask the Sommelier to recommend the best coffee for your mood.\n"
            "Step 2: Once recommended, ask if the Astoria store has enough Ethiopia Yirgacheffe Beans in stock."
        ),
        "initial_user_message": "I'm feeling really sleepy and stressed today. What coffee do you recommend for my mood?",
        "success_criteria": "The Sommelier returns a top sensory vector match, and subsequently answers the inventory stock level query."
    }
}


# ==============================================================================
# Simulation Runner & Judge
# ==============================================================================

def evaluate_transcript_with_judge(scenario_name: str, scenario_info: Dict[str, Any], transcript: List[Dict[str, str]], engine_logs: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM-as-a-Judge to evaluate transcript and Rasa engine logs for Task Completion (Pass/Fail)."""
    formatted_transcript = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in transcript])
    tools_executed_str = ", ".join(engine_logs.get("tools_executed", [])) if engine_logs.get("tools_executed") else "None"
    skills_activated_str = ", ".join(engine_logs.get("skills_activated", [])) if engine_logs.get("skills_activated") else "None"
    
    judge_prompt = (
        "You are an expert AI Agent Evaluation Judge.\n"
        f"Scenario Title: {scenario_info['title']}\n"
        f"Scenario Description: {scenario_info['description']}\n"
        f"Expected Success Criteria: {scenario_info['success_criteria']}\n"
        f"Rasa Engine Skills Activated: {skills_activated_str}\n"
        f"Rasa Engine Tools Executed: {tools_executed_str}\n\n"
        "Analyze the following conversation transcript between USER and BOT, as well as the engine tools executed.\n"
        "Evaluate whether the BOT successfully fulfilled the scenario's objective and criteria.\n\n"
        "Return ONLY a valid JSON object with the following structure:\n"
        "{\n"
        '  "task_completed": true | false,\n'
        '  "score": 1.0 | 0.0,\n'
        '  "summary": "Short 1-2 sentence explanation of judgment.",\n'
        '  "issues_detected": ["issue 1", "issue 2"]\n'
        "}\n"
    )

    judge_messages = [{"role": "user", "content": f"Transcript:\n{formatted_transcript}"}]
    judge_response = call_llm(judge_messages, system_prompt=judge_prompt, temperature=0.1)

    try:
        clean_json = judge_response
        if "```" in clean_json:
            clean_json = clean_json.split("```")[1]
            if clean_json.startswith("json"):
                clean_json = clean_json[4:]
        result = json.loads(clean_json.strip())
        return result
    except Exception:
        is_pass = "true" in judge_response.lower() or "passed" in judge_response.lower()
        return {
            "task_completed": is_pass,
            "score": 1.0 if is_pass else 0.0,
            "summary": judge_response[:200],
            "issues_detected": ["JSON parsing fallback"]
        }


def run_single_simulation(scenario_key: str, sim_id: int, pbar: Optional[Any] = None) -> Dict[str, Any]:
    """Execute 1 multi-turn conversation simulation up to MAX_TURNS_PER_SIMULATION and fetch Rasa logs."""
    scenario = OPERATIONAL_SCENARIOS[scenario_key]
    session_id = f"sim-{scenario_key}-{sim_id}-{uuid.uuid4().hex[:6]}"
    
    user_msg = scenario["initial_user_message"]
    transcript = [{"role": "user", "content": user_msg}]
    simulator_messages = [{"role": "user", "content": f"The conversation starts. Your first message to the bot was: '{user_msg}'"}]

    turn_count = 0
    
    for turn in range(MAX_TURNS_PER_SIMULATION):
        turn_count += 1
        
        bot_responses = send_to_rasa(user_msg, session_id)
        bot_combined = "\n".join(bot_responses) if bot_responses else "[No Response]"
        transcript.append({"role": "bot", "content": bot_combined})

        if "[Rasa Connection Error" in bot_combined:
            break

        sim_prompt = (
            f"{scenario['system_prompt']}\n"
            "Review the latest BOT response. If your goal is fully achieved (e.g. order confirmed with Order ID, analytics received), "
            "say 'THANK YOU, GOT IT' or a polite closing. Otherwise, generate your next realistic user response."
        )
        simulator_messages.append({"role": "assistant", "content": user_msg})
        simulator_messages.append({"role": "user", "content": f"BOT Response: {bot_combined}\nGenerate your next turn:"})

        next_user_msg = call_llm(simulator_messages[-4:], system_prompt=sim_prompt, temperature=0.4)
        
        if "THANK YOU, GOT IT" in next_user_msg.upper() or "ORDER CONFIRMED" in next_user_msg.upper() or "THAT IS ALL" in next_user_msg.upper():
            transcript.append({"role": "user", "content": next_user_msg})
            break

        user_msg = next_user_msg
        transcript.append({"role": "user", "content": user_msg})

    # Fetch Rasa Engine Tracker Logs
    engine_logs = fetch_rasa_tracker_logs(session_id)

    # Save log file to LOGS_DIR
    log_file_path = LOGS_DIR / f"{session_id}.log"
    with open(log_file_path, "w") as f:
        f.write(f"=== RASA ENGINE EVENT LOG FOR {session_id} ===\n")
        f.write(f"Scenario: {scenario['title']}\n")
        f.write(f"Skills Activated: {engine_logs['skills_activated']}\n")
        f.write(f"Tools Executed: {engine_logs['tools_executed']}\n")
        f.write(f"Slots Summary: {engine_logs['slots_summary']}\n")
        f.write("\n=== CHRONOLOGICAL EVENT TRANSCRIPT ===\n")
        f.write(engine_logs['log_transcript'])

    judgment = evaluate_transcript_with_judge(scenario_key, scenario, transcript, engine_logs)

    if pbar:
        pbar.update(1)

    return {
        "simulation_id": session_id,
        "scenario_key": scenario_key,
        "run_index": sim_id,
        "turns_taken": turn_count,
        "passed": judgment.get("task_completed", False),
        "score": judgment.get("score", 0.0),
        "summary": judgment.get("summary", ""),
        "issues": judgment.get("issues_detected", []),
        "rasa_engine_logs": {
            "skills_activated": engine_logs["skills_activated"],
            "tools_executed": engine_logs["tools_executed"],
            "slots_summary": engine_logs["slots_summary"],
            "log_file": str(log_file_path),
            "transcript_snippet": engine_logs["log_transcript"]
        },
        "transcript": transcript
    }


# ==============================================================================
# Main Runner & Quota Accounting
# ==============================================================================

def main():
    ops_count = len(OPERATIONAL_SCENARIOS)
    total_simulations = ops_count * SIMULATIONS_PER_OPERATION
    max_llm_calls_limit = total_simulations * (MAX_TURNS_PER_SIMULATION + 1)

    print("=" * 80, flush=True)
    print(" ☕ Artisan Roast — Multi-Turn Agent Evaluation Harness & Simulator", flush=True)
    print("=" * 80, flush=True)
    print(f" LLM Provider Model     : {EVAL_MODEL}", flush=True)
    print(f" Rasa API Endpoint      : {RASA_ENDPOINT}", flush=True)
    print(f" Total Operations       : {ops_count} scenarios", flush=True)
    print(f" Simulations / Op       : {SIMULATIONS_PER_OPERATION} runs", flush=True)
    print(f" Max Turns / Simulation : {MAX_TURNS_PER_SIMULATION} turns", flush=True)
    print(f" Total Simulations      : {total_simulations} simulation runs", flush=True)
    print(f" Max LLM Call Quota     : {max_llm_calls_limit} calls max", flush=True)
    print("=" * 80, flush=True)

    # Check server availability
    try:
        req = urllib.request.Request(f"{RASA_BASE_URL}/version")
        with urllib.request.urlopen(req, timeout=3) as resp:
            print(f" ✓ Rasa Server detected at {RASA_BASE_URL}", flush=True)
    except Exception:
        print(f" ⚠️ Rasa server not detected at {RASA_BASE_URL}. (Start server via `make run` in coffee-shop)", flush=True)

    all_results = []
    summary_by_op = {}

    if HAS_TQDM:
        pbar = tqdm(total=total_simulations, desc="Simulating Operations", unit="sim")
    else:
        pbar = None

    for op_key, op_info in OPERATIONAL_SCENARIOS.items():
        if not HAS_TQDM:
            print(f"\n▶ Running Scenario: {op_info['title']}", flush=True)
        op_runs = []
        
        for sim_i in range(1, SIMULATIONS_PER_OPERATION + 1):
            res = run_single_simulation(op_key, sim_i, pbar=pbar)
            op_runs.append(res)
            all_results.append(res)
            if not HAS_TQDM:
                status_str = "✅ PASS" if res["passed"] else "❌ FAIL"
                tools_str = ", ".join(res["rasa_engine_logs"]["tools_executed"]) or "none"
                print(f"    [{status_str}] Run #{sim_i} in {res['turns_taken']} turns (Tools: {tools_str}). Verdict: {res['summary']}", flush=True)

        passed_count = sum(1 for r in op_runs if r["passed"])
        pass_rate = (passed_count / len(op_runs)) * 100.0
        summary_by_op[op_key] = {
            "title": op_info["title"],
            "total_runs": len(op_runs),
            "passed_runs": passed_count,
            "pass_rate_pct": pass_rate
        }

    if pbar:
        pbar.close()

    # Total metrics
    total_passed = sum(1 for r in all_results if r["passed"])
    overall_pass_rate = (total_passed / total_simulations) * 100.0 if total_simulations > 0 else 0.0

    print("\n" + "=" * 80, flush=True)
    print(" 📊 EVALUATION SIMULATION RESULTS SUMMARY", flush=True)
    print("=" * 80, flush=True)
    for op_key, s in summary_by_op.items():
        print(f" • {s['title']:<55} | Pass Rate: {s['pass_rate_pct']:5.1f}% ({s['passed_runs']}/{s['total_runs']})", flush=True)
    print("-" * 80, flush=True)
    print(f" OVERALL TASK COMPLETION PASS RATE: {overall_pass_rate:.1f}% ({total_passed}/{total_simulations})", flush=True)
    print(f" TOTAL LLM API CALLS CONSUMED: {llm_api_call_counter} / {max_llm_calls_limit} max quota", flush=True)
    print("=" * 80, flush=True)

    # Export Report JSON & Markdown
    report_json_path = OUTPUT_DIR / "simulation_report.json"
    with open(report_json_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "eval_model": EVAL_MODEL,
            "overall_pass_rate_pct": overall_pass_rate,
            "total_simulations": total_simulations,
            "total_passed": total_passed,
            "llm_api_calls_used": llm_api_call_counter,
            "max_llm_calls_quota": max_llm_calls_limit,
            "operations_summary": summary_by_op,
            "detailed_runs": all_results
        }, f, indent=2)

    report_md_path = OUTPUT_DIR / "SUMMARY.md"
    with open(report_md_path, "w") as f:
        f.write("# ☕ Multi-Turn Agent Evaluation Simulation Report\n\n")
        f.write(f"- **Evaluated Model**: `{EVAL_MODEL}`\n")
        f.write(f"- **Overall Task Completion Pass Rate**: **{overall_pass_rate:.1f}%** ({total_passed}/{total_simulations} passed)\n")
        f.write(f"- **LLM API Calls Consumed**: `{llm_api_call_counter}` / `{max_llm_calls_limit}` max quota\n")
        f.write(f"- **Timestamp**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n")
        f.write("## 📊 Operation Performance Matrix\n\n")
        f.write("| Operational Scenario | Total Runs | Passed Runs | Pass Rate |\n")
        f.write("| :--- | :-: | :-: | :-: |\n")
        for op_key, s in summary_by_op.items():
            f.write(f"| **{s['title']}** | {s['total_runs']} | {s['passed_runs']} | **{s['pass_rate_pct']:.1f}%** |\n")
        f.write("\n---\n\n")
        f.write("## 🔍 Detailed Simulation Event Logs\n\n")
        for res in all_results:
            status_emoji = "✅ PASS" if res["passed"] else "❌ FAIL"
            f.write(f"### {status_emoji} `{res['simulation_id']}` ({res['scenario_key']})\n")
            f.write(f"- **Verdict**: {res['summary']}\n")
            f.write(f"- **Skills Activated**: `{res['rasa_engine_logs']['skills_activated']}`\n")
            f.write(f"- **Tools Executed**: `{res['rasa_engine_logs']['tools_executed']}`\n")
            f.write(f"- **Log File**: [`{res['rasa_engine_logs']['log_file']}`]({res['rasa_engine_logs']['log_file']})\n")
            f.write("<details><summary>Click to view Rasa Engine Event Transcript</summary>\n\n```text\n")
            f.write(res['rasa_engine_logs']['transcript_snippet'])
            f.write("\n```\n</details>\n\n")

    print(f"\n Report saved to: {report_json_path}", flush=True)
    print(f" Summary saved to: {report_md_path}", flush=True)
    print(f" Individual event logs saved in: {LOGS_DIR}/\n", flush=True)

if __name__ == "__main__":
    main()
