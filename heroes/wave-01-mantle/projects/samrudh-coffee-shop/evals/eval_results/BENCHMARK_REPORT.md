# Rasa Pro Mantle Agent Evaluation Benchmark Report ($X \rightarrow Y \rightarrow Z$)

This report documents the performance progression of the **Artisan Roast Coffee Shop Agent** across three development phases using the multi-turn dialogue evaluation harness.

---

## Phase Comparison Summary

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

## Phase Breakdown

### Phase X: Baseline (`rasa-pro==3.20.0.dev6`)
* **Overall Pass Rate**: **46.7%** (7/15)
* **API Calls**: 77 calls
* **Key Observations**: Single orders (Op 1) and sommelier recommendations (Op 5) succeeded reliably. However, multi-item consecutive orders (Op 2) and executive PIN authentication (Op 4) failed completely due to multi-turn field prompts and missing memory slots.

### Phase Y: Version Upgrade (`rasa-pro==3.20.0.dev9`)
* **Overall Pass Rate**: **20.0%** (3/15)
* **API Calls**: 78 calls
* **Key Observations**: Upgrading Rasa Pro introduced stricter engine schema validation on tool arguments (e.g. `category="coffee beans"` failed validation against `Beans`) and memory locks, temporarily causing a pass rate drop before skill adaptation.

### Phase Z: Refactored Skills & `complete_when` (`rasa-pro==3.20.0.dev9`)
* **Overall Pass Rate**: **80.0%** (12/15)
* **API Calls**: 71 calls
* **Key Improvements**:
  1. **Single-Turn Default Combination Prompting**: Reduced turn count and solved consecutive ordering failures (**0% $\rightarrow$ 100%**).
  2. **`complete_when` Frontmatter Mappings**: Handled skill lifecycle deterministically.
  3. **Category Normalization**: Fixed tool parameter validation errors (**0% $\rightarrow$ 100%** on Op 5).

---

## Security Compliance
All result data in this report is generated autonomously from synthetic ground-truth test data. No real API keys, credentials, or private tokens are stored.
