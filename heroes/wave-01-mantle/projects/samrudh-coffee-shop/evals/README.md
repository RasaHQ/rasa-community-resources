# Rasa Pro Mantle Agent Evaluation Suite & User Simulator

This evaluation suite provides an autonomous multi-turn dialogue simulator, LLM-as-a-Judge test harness, and interactive dashboard for benchmarking **Rasa Pro Mantle** conversational agents.

---

## Key Features

1. **Cross-Model Family Simulation**: Simulates dynamic user dialogues across multiple LLM provider families (OpenRouter DeepSeek V3, OpenAI, Gemini) and evaluates agent responses using customizable domain rubrics.
2. **API Call Quota & Cost Efficiency Tracking**: Monitors turn-by-turn LLM API call consumption and tracks cost/turn reductions across benchmark iterations.
3. **Interactive Web UI & Real-Time Traceability**: Includes a standalone server (`server.py`) and Web UI (`web/index.html`) at `http://localhost:8000` supplying live LLM call traceability, prompt inspection, tool payload debugging, and tracker log streaming.
4. **Grounding Using Ground Truth Dataset Assertions**: Connects to domain datasets and databases (`coffeeshop.db`) to perform post-dialogue state verification on created orders and updated inventory levels.

---

## Benchmark Study: $X \rightarrow Y \rightarrow Z$ Performance Evolution

We evaluated the Coffee Shop Agent across **5 operational dialogue scenarios** (15 multi-turn simulation runs per phase) using OpenRouter DeepSeek V3 as the user simulator and evaluation judge.

### Comparative Performance Matrix

| Operational Scenario | Phase X (Baseline - `dev6`) | Phase Y (Version Upgrade - `dev9`) | Phase Z (Refactored & `complete_when`) | Absolute Delta ($X \rightarrow Z$) |
| :--- | :-: | :-: | :-: | :-: |
| **1. Single Beverage Order** | **100.0%** (3/3) | **100.0%** (3/3) | **100.0%** (3/3) | **0.0%** |
| **2. Two Consecutive Orders** | **0.0%** (0/3) | **0.0%** (0/3) | **100.0%** (3/3) | **+100.0%** |
| **3. Group Order** | **33.3%** (1/3) | **0.0%** (0/3) | **66.7%** (2/3) | **+33.4%** |
| **4. CEO Admin Analytics & PIN** | **0.0%** (0/3) | **0.0%** (0/3) | **33.3%** (1/3) | **+33.3%** |
| **5. Sommelier & Store Inventory** | **100.0%** (3/3) | **0.0%** (0/3) | **100.0%** (3/3) | **0.0%** |
| **Overall Pass Rate** | **46.7%** (7/15) | **20.0%** (3/15) | **80.0%** (12/15) | **+33.3% vs X (+60.0% vs Y)** |
| **LLM API Calls Consumed** | 77 calls | 78 calls | **71 calls** | **-6 calls (-7.8%)** |

---

## Key Learnings & Rasa Pro Best Practices

1. **Single-Turn Combination Prompting**: Presenting complete default order combinations in a single turn eliminated turn exhaustion on consecutive/group orders (**0% -> 100% pass rate**).
2. **Native Rasa Pro `complete_when` Skill Gating**: Frontmatter `complete_when` mapping (`complete_when:\n  condition: "session.<skill>.<field>"`) deterministically completes active skills without unnecessary filler turns.
3. **Strict Tool Schema Validation**: Normalizing parameter strings (`"coffee beans"` -> `"Beans"`) prevents tool schema validation failures.

---

## Evaluation Folder Structure

```text
coffee-shop/evals/
├── .gitignore               # Excludes raw logs and .env files
├── .env.example             # Environment variable configuration template
├── README.md                # This guide & benchmark evaluation summary
├── eval_config.json         # Evaluation scenarios & ground-truth judge rubrics
├── eval_simulator.py        # Automated CLI simulator & event log extractor script
├── server.py                # Standalone HTTP server for Web UI dashboard & live LLM traceability
├── web/                     # Web UI dashboard frontend assets
│   └── index.html           # Interactive evaluation dashboard UI
└── eval_results/            # Benchmark report markdown
    └── BENCHMARK_REPORT.md
```

---

## How to Run the Evaluation Harness

### 1. Configure Environment Variables
Copy `.env.example` to `.env` and set your LLM API key:
```bash
cd coffee-shop/evals
cp .env.example .env
```

### 2. Launch Options

#### Option A: Command-Line Simulation
```bash
python3 eval_simulator.py
```

#### Option B: Interactive Web UI Dashboard & LLM Traceability Server
```bash
python3 server.py
```
Open **`http://localhost:8000`** to access the live dashboard, trace LLM API calls, inspect prompt payloads, and trigger test runs interactively.
