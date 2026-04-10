"""
Simplified Chemical Expert - Hardcoded Lookups

NO complex reasoning for chemicals. 
Only hardcoded A/B/C/D ratings for the 5 chemicals that matter.
Everything else → "Contact Enpro engineering"
"""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("enpro.models.chemical")


@dataclass
class ChemicalRating:
    """A/B/C/D rating with reasoning."""
    rating: str  # A, B, C, or D
    reasoning: str
    escalate: bool = False


class ChemicalExpert:
    """
    Hardcoded chemical compatibility - NO AI reasoning.
    
    Only handles these chemicals:
    - Sulfuric Acid (concentrated 98%)
    - MEK (Methyl Ethyl Ketone)
    - Ethylene Glycol
    - Hydrocarbons (general)
    - Corrosive service (general)
    
    Everything else: "Contact Enpro engineering with SDS"
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HARD CODED RATINGS - Source of truth, never calls AI
    # ═══════════════════════════════════════════════════════════════════════════
    HARDCODED = {
        "sulfuric acid": {
            "concentrated_98": {
                "Viton": ChemicalRating("C", "Marginal — verify concentration", False),
                "EPDM": ChemicalRating("C", "Marginal at high concentration", False),
                "Buna-N": ChemicalRating("D", "AVOID — degrades in concentrated acid", False),
                "Nylon": ChemicalRating("D", "Do NOT use — attacked by acid", False),
                "PTFE": ChemicalRating("A", "Fully fluorinated, chemically inert", False),
                "PVDF": ChemicalRating("A", "Excellent resistance", False),
                "316SS": ChemicalRating("D", "AVOID at high concentration — use Hastelloy C", True),
            }
        },
        "mek": {
            "standard": {
                "Viton": ChemicalRating("B", "Acceptable for ketones", False),
                "EPDM": ChemicalRating("D", "AVOID — swells significantly in ketones", False),
                "Buna-N": ChemicalRating("D", "AVOID — degrades in ketones", False),
                "PTFE": ChemicalRating("A", "Inert to ketones", False),
                "PVDF": ChemicalRating("A", "Good resistance", False),
                "316SS": ChemicalRating("A", "Compatible", False),
            }
        },
        "methyl ethyl ketone": {
            "standard": {
                "Viton": ChemicalRating("B", "Acceptable for ketones", False),
                "EPDM": ChemicalRating("D", "AVOID — swells significantly in ketones", False),
                "Buna-N": ChemicalRating("D", "AVOID — degrades in ketones", False),
                "PTFE": ChemicalRating("A", "Inert to ketones", False),
                "PVDF": ChemicalRating("A", "Good resistance", False),
                "316SS": ChemicalRating("A", "Compatible", False),
            }
        },
        "ethylene glycol": {
            "standard": {
                "Viton": ChemicalRating("A", "Excellent compatibility", False),
                "EPDM": ChemicalRating("A", "Excellent compatibility", False),
                "Buna-N": ChemicalRating("B", "Good — minor swelling possible", False),
                "PTFE": ChemicalRating("A", "Inert", False),
                "PVDF": ChemicalRating("A", "Excellent", False),
                "316SS": ChemicalRating("A", "Compatible", False),
            }
        },
        "hydrocarbon": {
            "aliphatic": {
                "Viton": ChemicalRating("A", "Excellent for aliphatic hydrocarbons", False),
                "EPDM": ChemicalRating("D", "AVOID — swells in hydrocarbons", True),
                "Buna-N": ChemicalRating("B", "Acceptable for aliphatic", False),
                "PTFE": ChemicalRating("A", "Inert", False),
                "PVDF": ChemicalRating("A", "Good", False),
                "316SS": ChemicalRating("A", "Compatible", False),
                "note": "Viton NOT recommended for aromatic hydrocarbons (benzene, toluene) or ketones",
            }
        },
        "corrosive": {
            "general": {
                "Viton": ChemicalRating("B", "Check specific chemical", False),
                "EPDM": ChemicalRating("B", "Check specific chemical", False),
                "Buna-N": ChemicalRating("C", "Limited — verify compatibility", False),
                "PTFE": ChemicalRating("A", "Generally excellent for corrosives", False),
                "PVDF": ChemicalRating("A", "Excellent for most corrosives", False),
                "316SS": ChemicalRating("A", "Standard for corrosive service — carbon steel NOT recommended", False),
            }
        }
    }
    
    # Materials to always include in ratings
    ALL_MATERIALS = ["Viton", "EPDM", "Buna-N", "PTFE", "316SS"]
    OPTIONAL_MATERIALS = ["Nylon", "PVDF"]
    
    def lookup(self, chemical: str, concentration: Optional[str] = None) -> Dict[str, Any]:
        """
        Hardcoded lookup - zero AI cost.
        
        Returns:
            - ratings: Dict of material -> rating
            - headline: Summary sentence
            - escalate: Whether engineering review required
            - escalation_reason: Why escalation needed
        """
        chemical_lower = chemical.lower().strip()
        
        # Check for escalation keywords first
        escalation_chemicals = ["hydrogen", "h2s", "hydrogen sulfide", "chlorine", "hf", "hydrofluoric", "lethal"]
        if any(kw in chemical_lower for kw in escalation_chemicals):
            return {
                "ratings": {},
                "headline": f"{chemical.title()} requires engineering review",
                "escalate": True,
                "escalation_reason": f"{chemical.title()} service requires engineering review. Contact Enpro with SDS.",
                "method": "hardcoded_escalation",
                "cost": 0.0
            }
        
        # Try exact match
        if chemical_lower in self.HARDCODED:
            return self._format_ratings(chemical, self.HARDCODED[chemical_lower])
        
        # Try partial match
        for known_chemical, data in self.HARDCODED.items():
            if known_chemical in chemical_lower or chemical_lower in known_chemical:
                return self._format_ratings(known_chemical, data)
        
        # Unknown chemical - escalate
        return {
            "ratings": {},
            "headline": f"{chemical.title()} — Contact Enpro engineering",
            "escalate": True,
            "escalation_reason": f"{chemical.title()} not in hardcoded compatibility matrix. Contact Enpro engineering with SDS for review.",
            "method": "unknown_chemical",
            "cost": 0.0
        }
    
    def _format_ratings(self, chemical: str, data: Dict) -> Dict[str, Any]:
        """Format hardcoded ratings into response structure."""
        # Get the first (and usually only) variant
        variant = list(data.values())[0]
        
        ratings = {}
        escalate = False
        escalation_reasons = []
        
        for material in self.ALL_MATERIALS + self.OPTIONAL_MATERIALS:
            if material in variant:
                rating_obj = variant[material]
                ratings[material] = {
                    "rating": rating_obj.rating,
                    "reasoning": rating_obj.reasoning
                }
                if rating_obj.escalate:
                    escalate = True
                    escalation_reasons.append(f"{material} rated {rating_obj.rating}: {rating_obj.reasoning}")
        
        # Generate headline
        a_rated = [m for m, r in ratings.items() if r["rating"] == "A"]
        d_rated = [m for m, r in ratings.items() if r["rating"] == "D"]
        
        if d_rated:
            headline = f"For {chemical}: Avoid {', '.join(d_rated)}. Use {', '.join(a_rated[:2])}."
        else:
            headline = f"For {chemical}: {', '.join(a_rated[:3])} are all A-rated."
        
        if escalate:
            headline += " Engineering review recommended."
        
        return {
            "ratings": ratings,
            "headline": headline,
            "escalate": escalate,
            "escalation_reason": "; ".join(escalation_reasons) if escalate else None,
            "method": "hardcoded_lookup",
            "cost": 0.0
        }
    
    def quick_check(self, chemical: str, material: str) -> Optional[str]:
        """Quick single lookup - returns A/B/C/D or None."""
        result = self.lookup(chemical)
        ratings = result.get("ratings", {})
        if material in ratings:
            return ratings[material]["rating"]
        return None


# Global instance
_chemical_expert: Optional[ChemicalExpert] = None


def get_chemical_expert() -> ChemicalExpert:
    """Get the global chemical expert instance."""
    global _chemical_expert
    if _chemical_expert is None:
        _chemical_expert = ChemicalExpert()
    return _chemical_expert
