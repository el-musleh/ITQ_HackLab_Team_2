# AI API Smart Decision-Making — Future Enhancement

**Status:** Not implemented — documented for future consideration  
**Date:** June 21, 2026

---

## Overview

The current robot uses a hardcoded finite state machine (`src/control/state_machine.py`) running at 20 Hz with deterministic, rule-based decisions: greedy nearest-ball selection, fixed pan-sweep search, static recovery maneuvers, and no time awareness. An LLM API (OpenRouter / DeepSeek) could be called asynchronously at state transition points to add context-aware strategic reasoning — improving ball selection, search efficiency, recovery behavior, and time management without touching the real-time control loop.

## Current Decision-Making Limitations

| Area | Current Behavior | Limitation |
|------|-----------------|------------|
| **Ball selection** | `world_map.get_nearest_ball()` — always closest | Ignores obstacles, clusters, time budget |
| **Search** | Fixed pan sweep (-90° to +90°), rotate 180°, repeat | No coverage awareness, re-scans visited areas |
| **Recovery** | Reverse 0.5s → turn 1.0s, alternating left/right | Same maneuver regardless of context |
| **Time strategy** | Same behavior from t=0 to t=300s | No adaptation as clock runs out |
| **Failure learning** | After 3 retries, ball marked unreachable | No pattern recognition across failures |
| **Basket search** | Turn left until found, 2s timeout → recovery | Doesn't use last known basket position |
| **Obstacle avoidance** | Reactive: left/right/reverse by pixel count | No path planning around known obstacles |

## Integration Architecture

```
┌─────────────────────────────────────────────────────┐
│                 State Machine (20 Hz)                │
│   Runs real-time control loop as usual (unchanged)   │
└──────────────┬──────────────────────────┬───────────┘
               │ At decision points        │ Telemetry
               ▼                           ▼
┌──────────────────────────┐  ┌────────────────────────┐
│   AI Decision Broker     │  │   Run Logger / Memory   │
│  (async, non-blocking)   │  │  (balls found, fails,   │
│  Called at state transitions│   time, obstacles hit)  │
└──────────┬───────────────┘  └────────────────────────┘
           │ HTTP request (1-3s latency OK)
           ▼
┌──────────────────────────┐
│  OpenRouter / DeepSeek   │
│  LLM API (JSON mode)     │
└──────────────────────────┘
```

**Key principle:** The LLM is never in the 20 Hz control loop. It is called at state transition points (every 2–60 seconds) where a strategic decision is needed. The state machine continues running while the API call is in-flight, and applies the LLM's recommendation when it arrives. If the API fails or times out, the robot falls back to existing rule-based logic.

---

## Idea Catalog

### 1. Strategic Ball Selection (Replace Greedy Nearest)

**Current:** `world_map.get_nearest_ball()` always picks the closest ball.  
**AI-enhanced:** Ask the LLM to pick the best ball given all known ball positions, colors, robot pose, obstacle positions, time remaining, and balls already collected.

**Example prompt:**
```
Robot at (0.8, 1.2, heading 45°). Known balls:
- #3 at (1.5, 0.3) blue, confidence 0.9
- #7 at (0.2, 1.6) red, confidence 0.7
- #9 at (1.7, 1.5) silver, confidence 0.5
Obstacle at (1.0, 0.8, 30x40cm). 180s remaining. 5 balls collected.
Which ball should the robot collect next? Reply JSON: {"ball_id": N, "reason": "..."}
```

**Benefit:** Avoids balls behind obstacles, prioritizes clusters, considers time cost.

---

### 2. Adaptive Search Strategy

**Current:** Fixed pan sweep then rotate 180° and sweep again.  
**AI-enhanced:** LLM analyzes coverage map and suggests which direction to explore next, whether to do a wide sweep or targeted look, and which unvisited area is most promising.

**Benefit:** Faster arena coverage, finds balls quicker, avoids re-scanning visited areas.

---

### 3. Context-Aware Recovery

**Current:** Always reverse 0.5s → turn 1.0s (alternating left/right).  
**AI-enhanced:** Feed the LLM the recovery context — what state failed, robot pose, nearby obstacles/boundaries, and recovery history.

**Example:**
```
Recovery needed. Robot stuck at (1.6, 0.1) near east boundary.
Last action: approaching ball #5. Tried: reverse+turn_left (failed).
Obstacle 2m ahead. Basket at center.
Recovery options: reverse_long, turn_right_90, back_away_left, abort_ball
Reply JSON: {"action": "...", "params": {...}}
```

**Benefit:** Smarter escapes — turn away from walls, abandon unreachable balls sooner.

---

### 4. Time-Aware Strategy Adaptation

**Current:** Same behavior from t=0 to t=300s.  
**AI-enhanced:** LLM adjusts strategy based on time budget:

| Time Window | Strategy |
|-------------|----------|
| 0–120s | Methodical search, collect all colors, careful approach |
| 120–240s | Prioritize nearby balls, skip far ones, faster approach |
| 240–300s | Rush mode — only grab very close balls, skip deposit if basket is far |

**Benefit:** Maximizes score within the 5-minute limit.

---

### 5. Dynamic PID / Speed Tuning

**Current:** Fixed `kp=3.0, ki=0.0, kd=0.5`, fixed `approach_speed=0.15`.  
**AI-enhanced:** After each successful/failed approach, LLM analyzes tracking performance and suggests PID gain adjustments or speed changes.

**Example:**
```
Last approach: ball at 30cm, took 4.2s, oscillated 3 times before centering.
Current PID: kp=3.0, kd=0.5. Approach speed: 0.15.
Suggest adjustments. Reply JSON: {"kp": ..., "kd": ..., "approach_speed": ...}
```

**Benefit:** Adapts to arena conditions (slippery floor, lighting affecting detection range).

---

### 6. Natural Language Pre-Run Configuration

**Current:** Manually edit `config.yaml` before each run.  
**AI-enhanced:** Operator describes strategy in natural language, LLM generates config overrides.

**Example:**
```
Operator: "Bright lighting today. Focus on blue and red, skip silver
          if time is short. Be extra careful near the left wall."
LLM → {"balls": {"priority": ["blue", "red", "silver"]},
        "obstacles": {"caution_zones": ["left"]},
        "time_strategy": {"skip_color_after_sec": 200, "color": "silver"}}
```

**Benefit:** Quick strategy changes without code edits.

---

### 7. Failure Pattern Recognition & Adaptation

**Current:** After 3 failed recovery attempts, ball is marked unreachable. No learning.  
**AI-enhanced:** LLM analyzes failure patterns across the run:

- "Robot failed 3 times near the northeast corner — avoid that quadrant"
- "Silver balls have 60% pickup failure rate — adjust arm pose for silver"
- "Basket detection fails when approaching from the south — approach from west"

**Benefit:** Robot gets smarter during a single run.

---

### 8. Smart Basket Re-Localization

**Current:** If basket not found, turn left until found (2s timeout → recovery).  
**AI-enhanced:** LLM uses world map to suggest navigating to last known basket position, choosing an approach angle that worked before, or deciding between a 360° scan vs targeted search.

**Benefit:** Less time wasted searching for basket.

---

### 9. Multi-Ball Batching (Collect Multiple Before Deposit)

**Current:** Always collect 1 ball → go to basket → deposit → search again.  
**AI-enhanced:** LLM decides whether to grab another nearby ball before going to basket.

**Note:** Hardware constraint — JETANK gripper holds 1 cap. Viable only if gripper can hold 2–3 small caps, or if a "scoop" approach is used.

**Benefit:** Fewer trips to basket = more balls collected in 5 minutes.

---

### 10. Obstacle Path Planning

**Current:** Reactive avoidance — see obstacle, reverse/turn, continue.  
**AI-enhanced:** LLM plans a path around known obstacles using world map obstacle positions, computes detour waypoints, and feeds them to the navigator.

**Benefit:** Smoother navigation, fewer collisions, less time in recovery.

---

### 11. Confidence-Based Detection Filtering

**Current:** Trusts any detection that passes HSV + circularity filters.  
**AI-enhanced:** LLM assesses detection confidence — e.g., "Ball detected at extreme camera pan angle with small area — likely false positive" or "Silver HSV is unreliable in high-light conditions."

**Benefit:** Fewer wild goose chases after false positives.

---

### 12. Post-Run Analysis & Auto-Tuning

**Current:** Manual review of logs after run.  
**AI-enhanced:** After each run (or simulation), feed full telemetry to LLM — timeline of states, balls found/collected/missed, recovery events, time per ball.

**LLM outputs:** Suggested config changes, identified failure modes, strategy recommendations.

**Benefit:** Rapid iteration between simulation runs. Robot improves autonomously.

---

### 13. Vision-Language Scene Understanding (VLM)

**Current:** Pure HSV color segmentation — fails with lighting changes, reflections.  
**AI-enhanced:** Send a downscaled camera frame to a VLM (e.g., GPT-4o via OpenRouter) to describe what it sees — balls, obstacles, basket, walls. Use VLM output to cross-validate HSV detections or as fallback when HSV returns nothing.

**Constraint:** High latency (2–5s), only usable at decision points. Best for search state when HSV finds nothing.

**Benefit:** Robustness against lighting changes. Fallback when HSV fails entirely.

---

### 14. Natural Language Telemetry & Debug Narration

**Current:** Raw log lines: `State -> COLLECT_BALL (from CHECK_FOR_BALL)`  
**AI-enhanced:** LLM generates human-readable narration:

- "The robot spotted a red ball 25cm ahead and is now approaching it."
- "WARNING: Robot has been in RECOVERY for 8s near the northeast corner — 2nd recovery in this area."

**Benefit:** Easier debugging during competition.

---

### 15. Simulation-Based Strategy Optimization

**Current:** Run simulation with fixed parameters, manually inspect results.  
**AI-enhanced:** LLM acts as an optimizer — run sim, feed results to LLM, get parameter changes, re-run, repeat.

**Benefit:** Automated hyperparameter tuning for PID, timeouts, speeds, search patterns.

---

### 16. Dynamic State Machine Extension

**Current:** 8 fixed states, hardcoded transitions.  
**AI-enhanced:** LLM suggests transitional behaviors at runtime:

- "If ball is lost during approach but another ball is visible, switch target instead of recovery"
- "If time < 30s and carrying a ball, go directly to basket instead of searching"

**Implementation:** Add an "AI override" hook in `tick()` that can modify `next_state` based on LLM guidance.

**Benefit:** Flexible behavior without code changes. Handles edge cases the FSM wasn't designed for.

---

### 17. Arena Mapping Intelligence

**Current:** `WorldMap` tracks ball positions and visited cells with simple grid.  
**AI-enhanced:** LLM reasons about the arena layout:

- "Balls seem clustered in the south region — prioritize exploring south"
- "The northeast corner has been visited 3 times with no balls — deprioritize"
- "Obstacles form a wall between robot and basket — go around the north side"

**Benefit:** More efficient exploration. Better spatial reasoning than simple nearest-cell.

---

## Priority Assessment

| Priority | Idea | Impact | Effort | Latency OK? |
|----------|------|--------|--------|-------------|
| **P0** | #1 Strategic Ball Selection | High | Low | Yes (at transition) |
| **P0** | #3 Context-Aware Recovery | High | Medium | Yes (at recovery) |
| **P0** | #4 Time-Aware Strategy | High | Low | Yes (check every 30s) |
| **P1** | #2 Adaptive Search | Medium | Medium | Yes (at search start) |
| **P1** | #7 Failure Pattern Recognition | Medium | Medium | Yes (at failures) |
| **P1** | #8 Smart Basket Re-Localization | Medium | Low | Yes (at basket search) |
| **P1** | #12 Post-Run Analysis | High | Low | Yes (after run) |
| **P2** | #5 Dynamic PID Tuning | Medium | Medium | Yes (between balls) |
| **P2** | #6 NL Pre-Run Config | Medium | Low | Yes (before run) |
| **P2** | #10 Obstacle Path Planning | Medium | High | Yes (at navigation) |
| **P2** | #16 Dynamic FSM Extension | Medium | High | Yes (at transitions) |
| **P3** | #9 Multi-Ball Batching | Low | Medium | Yes (hardware-limited) |
| **P3** | #11 Confidence Filtering | Low | Medium | Borderline |
| **P3** | #13 VLM Scene Understanding | High | High | 2–5s per call |
| **P3** | #14 Debug Narration | Low | Low | Yes (async) |
| **P3** | #15 Sim Optimization | High | High | Yes (offline) |
| **P3** | #17 Arena Mapping Intelligence | Medium | High | Yes (at exploration) |

---

## Implementation Sketch

### New module: `src/control/ai_broker.py`

```python
import json
import requests
from threading import Thread, Event

class AIBroker:
    """Async LLM decision broker — non-blocking calls to OpenRouter/DeepSeek."""

    def __init__(self, api_key, model="deepseek/deepseek-chat",
                 base_url="https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._pending = None
        self._result = None
        self._thread = None

    def request_decision(self, system_prompt, context_dict, schema=None):
        """Fire async request. Result available via get_result()."""
        self._result = None
        self._pending = Event()
        self._thread = Thread(
            target=self._call_api,
            args=(system_prompt, context_dict, schema)
        )
        self._thread.daemon = True
        self._thread.start()

    def _call_api(self, system_prompt, context_dict, schema):
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(context_dict)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
                "max_tokens": 500,
            }
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=5.0,
            )
            self._result = json.loads(
                resp.json()["choices"][0]["message"]["content"]
            )
        except Exception as e:
            self._result = {"error": str(e)}
        finally:
            self._pending.set()

    def get_result(self):
        """Return result if ready, else None."""
        if self._pending and self._pending.is_set():
            return self._result
        return None

    def is_ready(self):
        return self._pending is not None and self._pending.is_set()
```

### Integration in `state_machine.py`

At key transition points (e.g., `_state_check_for_ball`), before selecting a ball:

```python
def _state_check_for_ball(self, frame, pose):
    # ... existing detection logic ...

    if balls:
        # Ask AI broker for best ball selection (async)
        if self.ai_broker and not self.ai_broker.is_ready():
            context = self._build_decision_context(balls, pose)
            self.ai_broker.request_decision(BALL_SELECTION_PROMPT, context)
            return CHECK_FOR_BALL  # come back next tick

        if self.ai_broker and self.ai_broker.is_ready():
            result = self.ai_broker.get_result()
            if result and 'ball_id' in result:
                selected = self._select_ball_by_id(result['ball_id'], balls)
                if selected:
                    self.current_ball = self._ball_to_dict(selected)
                    return COLLECT_BALL

        # Fallback: greedy nearest (existing behavior)
        balls_sorted = sorted(balls, key=lambda b: b[2])
        self.current_ball = self._ball_to_dict(balls_sorted[0])
        return COLLECT_BALL
```

### Config addition in `config.yaml`

```yaml
ai:
  enabled: true
  api_key: "sk-or-..."  # or env var OPENROUTER_API_KEY
  base_url: "https://openrouter.ai/api/v1"
  model: "deepseek/deepseek-chat"
  timeout_sec: 5.0
  fallback_to_rules: true  # If API fails, use existing rule-based logic
  decision_points:
    ball_selection: true
    recovery_strategy: true
    search_direction: true
    time_strategy: true
```

---

## Key Constraints & Risks

| Constraint | Details |
|------------|---------|
| **Latency** | API calls take 1–5s. Must be async and non-blocking. State machine keeps running. |
| **WiFi reliability** | Robot connects via WiFi — API may fail mid-run. Always fallback to rule-based logic. |
| **Cost** | DeepSeek is very cheap (~$0.14/M tokens). A 5-minute run with ~20 API calls ≈ $0.01. |
| **Jetson Nano** | No local LLM inference. All calls go to cloud API via WiFi. |
| **Rate limits** | OpenRouter has rate limits. 20 calls in 5 minutes is well within limits. |
| **Determinism** | Use `temperature=0.3` for consistent decisions. Not fully deterministic but stable. |
| **Safety** | LLM never controls motors directly. It only influences state transitions and parameters. Safety layer (`_update_safety`) always runs first and overrides. |

---

## Recommendation

The current rule-based FSM is sufficient for the competition — it is deterministic, debuggable, and has no external dependencies. The AI API integration ideas above are best pursued **post-competition** as an enhancement for more adaptive behavior.

If pursued, start with the three P0 ideas (#1 Strategic Ball Selection, #3 Context-Aware Recovery, #4 Time-Aware Strategy) as they offer the highest impact-to-effort ratio. Test in simulation (`src/simulation/`) before running on the real robot, and always maintain the rule-based fallback for competition safety.

**Priority:** Low — pursue only after the core FSM is stable and tested on the real robot.
