#!/usr/bin/env python3
"""
Six Thinking Hats Reasoning Engine for Antigravity Web Hub.
Applies Dr. Edward de Bono's 360-degree multi-perspective cognitive framework to pressure-test software architectures and plans.
"""

import sys
import json
from typing import Dict, Any

HATS = {
    "white_hat": {
        "title": "White Hat (Facts & Objective Data)",
        "focus": "Information requirements, verified metrics, latency targets, API contracts, and verifiable constraints."
    },
    "yellow_hat": {
        "title": "Yellow Hat (Optimism & Value Proposition)",
        "focus": "Architectural benefits, scalability advantages, developer productivity upsides, and cost savings."
    },
    "black_hat": {
        "title": "Black Hat (Risks & Vulnerability Audit)",
        "focus": "Potential failure modes, race conditions, single points of failure, rate limits (HTTP 429), and security flaws."
    },
    "red_hat": {
        "title": "Red Hat (Intuition & Developer Feel)",
        "focus": "Developer experience, UI/UX friction, cognitive load, aesthetic elegance, and developer trust."
    },
    "green_hat": {
        "title": "Green Hat (Creative Leapfrog Alternatives)",
        "focus": "Out-of-the-box approaches, modern open-source libraries, architectural shortcuts, and novel paradigms."
    },
    "blue_hat": {
        "title": "Blue Hat (Synthesis & Execution Roadmap)",
        "focus": "Actionable step-by-step roadmap, test-driven validation criteria, and definitive next steps."
    }
}

def format_six_hats_prompt(topic: str, context: str = "") -> str:
    """Generates a structured prompt injection template for 360-degree model evaluation."""
    lines = [
        f"### 🎩 Six Thinking Hats Evaluation: {topic}",
        ""
    ]
    if context:
        lines.append(f"**Context**: {context}\n")

    for key, hat in HATS.items():
        lines.append(f"#### {hat['title']}")
        lines.append(f"*Focus*: {hat['focus']}\n")

    return "\n".join(lines)

if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "Cloud Architecture Proposal"
    print(format_six_hats_prompt(t))
