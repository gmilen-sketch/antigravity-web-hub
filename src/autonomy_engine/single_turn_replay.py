import time
import json
from typing import Dict, Any, List, Optional, Callable

class SingleTurnReplayEngine:
    def __init__(self, inference_fn: Optional[Callable[[List[Dict[str, str]]], str]] = None):
        self.inference_fn = inference_fn or self._default_mock_inference

    @staticmethod
    def _default_mock_inference(messages: List[Dict[str, str]]) -> str:
        # Standard mock inference validating fast execution
        return "I will use the verified tool and follow strict schema constraints."

    def replay_turn(self, frozen_context: List[Dict[str, str]], candidate_prompt_patch: str, oracle_validator: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        start_t = time.time()
        
        # Inject candidate patch as system instruction
        augmented_context = [
            {"role": "system", "content": candidate_prompt_patch}
        ] + frozen_context

        # Execute 1-turn inference
        response_text = self.inference_fn(augmented_context)
        latency_ms = (time.time() - start_t) * 1000.0

        is_valid = True
        if oracle_validator:
            is_valid = oracle_validator(response_text)

        return {
            "passed": is_valid,
            "latency_ms": round(latency_ms, 2),
            "response": response_text,
            "fast_turn_pass": latency_ms < 2000.0 # Assert sub-2 second turnaround
        }
