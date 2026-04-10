"""
Enpro Filtration Mastermind — Context Resolution Layer

Resolves pronouns, validates application fit, and enriches messages
BEFORE they reach the intent classifier or model router.

Handles:
- "compare those" → resolves to specific part numbers from last turn
- "does this work for medical?" → validates referenced part against application
- "will that fit brewery?" → checks specs against application requirements
"""

import logging
import re
from typing import Dict, List, Optional, Any

from search import search_products, lookup_part

logger = logging.getLogger("enpro.context_resolver")

# Application requirements for validation
APPLICATION_REQUIREMENTS = {
    "medical": {
        "keywords": ["medical", "hospital", "patient", "healthcare", "merv", "ashrae", "cleanroom"],
        "min_merv": 14,
        "invalid_keywords": ["hydraulic", "oil", "150 psi"],
        "description": "medical/healthcare HVAC",
    },
    "brewery": {
        "keywords": ["brewery", "beer", "yeast", "fermentation", "wort", "mash", "brewing"],
        "preferred_media": ["depth sheet", "membrane", "absolute"],
        "certifications": ["FDA", "3-A", "NSF 61"],
        "description": "brewery/beverage",
    },
    "hydraulic": {
        "keywords": ["hydraulic", "oil", "lube", "hydraulics"],
        "min_psi": 100,
        "description": "hydraulic systems",
    },
    "hvac": {
        "keywords": ["hvac", "air", "ventilation", "air handler", "ahu"],
        "description": "HVAC air filtration",
    },
    "pharmaceutical": {
        "keywords": ["pharma", "pharmaceutical", "sterile", "aseptic"],
        "preferred_media": ["PTFE", "PES", "absolute"],
        "description": "pharmaceutical",
    },
    "data_center": {
        "keywords": ["data center", "server room", "it cooling"],
        "description": "data center cooling",
    },
}

# Pronoun patterns
PRONOUN_PATTERNS = [
    "those", "these", "them", "they", "it",
    "this part", "that part", "those parts", "these parts",
    "those filters", "these filters", "that filter", "this filter",
    "compare those", "compare them", "compare these",
]

# Validation question patterns
VALIDATION_PATTERNS = [
    r"does\s+(?:this|that|it)\s+work",
    r"will\s+(?:this|that|it)\s+work",
    r"is\s+(?:this|that|it)\s+(?:good|suitable|ok|right)\s+for",
    r"can\s+(?:i|we)\s+use\s+(?:this|that|it)\s+(?:for|in|with)",
    r"would\s+(?:this|that|it)\s+(?:work|fit|be\s+ok)",
    r"(?:this|that|it)\s+(?:work|fit|suitable)\s+for",
]


class ContextResolver:
    """Resolves references and validates applications before routing."""

    def __init__(self, cosmos_memory):
        self.memory = cosmos_memory

    async def resolve_message(self, message: str, session_id: str) -> Dict:
        """
        Resolve all context from a raw user message.
        Returns structured analysis with resolved entities.
        """
        msg_lower = message.lower()

        analysis = {
            "raw_message": message,
            "resolved_message": message,
            "intent": None,
            "referenced_parts": [],
            "referenced_application": None,
            "is_validation_question": False,
            "has_coreference": False,
        }

        # 1. Detect pronouns
        has_pronoun = any(p in msg_lower for p in PRONOUN_PATTERNS)

        if has_pronoun and session_id:
            # Resolve from Cosmos
            parts = await self.memory.resolve_coreference(session_id, message)
            if parts:
                analysis["referenced_parts"] = parts
                analysis["has_coreference"] = True
                # Rewrite message with resolved parts
                parts_str = ", ".join(parts)
                analysis["resolved_message"] = f"{message} [Context: referring to {parts_str}]"
                logger.info(f"Resolved coreference: {message} → parts {parts}")

        # 2. Detect application context
        for app_name, app_info in APPLICATION_REQUIREMENTS.items():
            if any(kw in msg_lower for kw in app_info["keywords"]):
                analysis["referenced_application"] = app_name
                break

        # 3. Detect validation questions
        for pattern in VALIDATION_PATTERNS:
            if re.search(pattern, msg_lower):
                analysis["is_validation_question"] = True
                analysis["intent"] = "validate_application"
                break

        # 4. Set intent for compare with resolved parts
        if analysis["has_coreference"] and "compare" in msg_lower:
            analysis["intent"] = "compare"

        return analysis

    async def validate_application_fit(
        self, part_number: str, application: str, df=None
    ) -> Dict:
        """Check if a specific part fits a specific application."""
        part = None
        if df is not None:
            part = lookup_part(df, part_number)

        if not part:
            return {
                "fits": None,
                "reason": f"Could not find {part_number} in catalog",
                "part": None,
                "alternatives": [],
            }

        req = APPLICATION_REQUIREMENTS.get(application, {})
        mismatches = []
        desc = str(part.get("Description", "")).lower()
        product_type = str(part.get("Product_Type", "")).lower()

        # Medical validation
        if application == "medical":
            if "hydraulic" in desc or "oil" in desc:
                mismatches.append(
                    f"{part_number} is a hydraulic/oil filter, not suitable for medical HVAC"
                )
            max_psi = part.get("Max_PSI", "")
            if max_psi and float(max_psi or 0) > 200:
                mismatches.append(
                    f"Rated for {max_psi} PSI — this is an industrial/hydraulic element, not HVAC"
                )

        # Hydraulic validation
        if application == "hydraulic":
            min_psi = req.get("min_psi", 100)
            max_psi = float(part.get("Max_PSI", 0) or 0)
            if max_psi > 0 and max_psi < min_psi:
                mismatches.append(
                    f"Rated for {max_psi} PSI, hydraulic systems typically need {min_psi}+ PSI"
                )

        if mismatches:
            alternatives = await self._find_alternatives(application, part_number, df)
            return {
                "fits": False,
                "reason": "; ".join(mismatches),
                "part": part,
                "alternatives": alternatives,
            }

        return {"fits": True, "reason": "Meets requirements", "part": part, "alternatives": []}

    async def _find_alternatives(
        self, application: str, exclude_pn: str, df=None
    ) -> List[Dict]:
        """Find alternatives that fit the application."""
        if df is None:
            return []

        req = APPLICATION_REQUIREMENTS.get(application, {})
        query = f"{req.get('description', application)} filter"

        result = search_products(df, query, max_results=5)
        alternatives = [
            p
            for p in result.get("results", [])
            if p.get("Part_Number", "") != exclude_pn
        ]
        return alternatives[:3]
