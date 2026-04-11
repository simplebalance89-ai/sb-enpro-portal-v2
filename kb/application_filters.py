"""
Application Filters — John's KB as pandas query parameters.

This file turns John's technical knowledge into STRUCTURED FILTER PARAMETERS
that narrow the catalog BEFORE any LLM fires. No prose in prompts — just
pandas-friendly rules per Application bucket.

Source: kb/filtration_reference.json (parsed into filter params 2026-04-11)
Review: Peter should correct/tune these values based on John's expertise
        after the Monday demo. This is the "good enough for ship" version.

Usage:
    from kb.application_filters import APPLICATION_FILTERS
    rules = APPLICATION_FILTERS["Food & Beverage"]
    # rules["preferred_manufacturers"] → ["Filtrox", "Pall"]
    # rules["micron_range"] → (0.45, 1.0)
"""

from typing import TypedDict, Optional


class FilterRules(TypedDict, total=False):
    preferred_manufacturers: list[str]
    preferred_media: list[str]
    preferred_product_types: list[str]
    micron_range: tuple[float, float]          # strict window
    fallback_micron_range: tuple[float, float] # if strict returns zero
    required_certs: list[str]                   # display only (catalog lacks cert field)
    escalation_keywords: list[str]              # phrases that bump to a different bucket
    typical_questions: list[str]                # pre-authored clarifying questions
    notes: str                                  # John's context for the bucket


APPLICATION_FILTERS: dict[str, FilterRules] = {

    "Food & Beverage": {
        "preferred_manufacturers": ["Filtrox", "Pall"],
        "preferred_media": ["Cellulose", "PES", "PTFE", "Polypropylene"],
        "preferred_product_types": ["Filter Sheet", "Filter Cartridge", "Filter Element", "Filter"],
        "micron_range": (0.45, 1.0),
        "fallback_micron_range": (0.1, 10.0),
        "required_certs": ["FDA", "3-A", "NSF 61"],
        "escalation_keywords": ["WFI", "pharma sterile", "validated sterile"],
        "typical_questions": [
            "What are you filtering — wort, beer, wine, or finished product?",
            "What's your clarity target — visual polish or a specific NTU?",
            "What sheet format do they run — 40x40 cm, 20x20, or smaller?",
            "Is this rough filtration or final polish?",
        ],
        "notes": "Filtrox is the primary depth-sheet brand. Beer/wine target 0.45-1.0 µm for clarity. FDA and 3-A are standard; NSF 61 required only if potable water contact.",
    },

    "Pharmaceutical": {
        "preferred_manufacturers": ["Pall"],
        "preferred_media": ["PES", "PTFE"],  # Absolute only for sterile — never nominal, never PVDF except solvent
        "preferred_product_types": ["Filter Cartridge", "Filter Element", "Membrane"],
        "micron_range": (0.1, 0.45),
        "fallback_micron_range": (0.05, 1.0),
        "required_certs": ["Validated", "Bacterial Challenge Tested"],
        "escalation_keywords": ["non-sterile", "aqueous only"],
        "typical_questions": [
            "Sterile duty or pre-filtration stage?",
            "Steam sterilization or gamma irradiation?",
            "What validation documentation do they need?",
            "What's the fluid — buffer, API, WFI, or something else?",
        ],
        "notes": "Absolute-rated PES or PTFE ONLY for sterile. 0.2 µm is the industry standard. Never nominal for sterile duty. Validation required.",
    },

    "Hydraulic": {
        "preferred_manufacturers": ["Pall", "Schroeder", "Donaldson", "Parker"],
        "preferred_media": ["Microglass", "Glass Fiber"],
        "preferred_product_types": ["Filter Element", "Filter Cartridge"],
        "micron_range": (3, 25),
        "fallback_micron_range": (1, 100),
        "required_certs": [],
        "escalation_keywords": ["pulsating flow", "pressure above 150 psi system"],
        "typical_questions": [
            "What's your system operating pressure and flow rate?",
            "What fluid — mineral oil, synthetic, or fire-resistant?",
            "What ISO cleanliness target (16/14/11 or tighter)?",
            "What's your current change-out interval — time or delta-P?",
        ],
        "notes": "Microglass absolute for critical service. ISO 16/14/11 is the typical target. 3-10 µm absolute rating. Max DP 35-50 psid before collapse risk.",
    },

    "Oil & Gas": {
        "preferred_manufacturers": ["Pall"],
        "preferred_media": ["Microglass", "Glass Fiber", "316 Stainless Steel"],
        "preferred_product_types": ["Filter Element", "Filter Cartridge", "Coalescer", "Separator"],
        "micron_range": (1, 25),
        "fallback_micron_range": (0.5, 100),
        "required_certs": ["NACE MR0175"],  # For sour service — flagged but not filtered
        "escalation_keywords": ["H2S", "HF", "hydrogen service", "NACE", "sour water", "sour service"],
        "typical_questions": [
            "What process — amine treating, glycol dehydration, condensate, or sour water?",
            "Are they dealing with H2S or sour service? (escalate to engineering if yes)",
            "What's the operating temperature and pressure?",
            "What contamination issue are they trying to solve — HC carryover, particulates, or salt?",
        ],
        "notes": "Amine foaming → Pall LLS or LLH coalescer (HC contamination is the root cause). Glycol dehy → SepraSol Plus + Ultipleat HF + Marksman. H2S / hydrogen / NACE always escalate.",
    },

    "Water Treatment": {
        "preferred_manufacturers": ["Pall", "3M", "Filtrox"],
        "preferred_media": ["Polypropylene", "PES", "Cellulose"],
        "preferred_product_types": ["Filter Cartridge", "Filter Element", "Bag Filter"],
        "micron_range": (0.5, 25),
        "fallback_micron_range": (0.2, 100),
        "required_certs": ["NSF 61"],  # Mandatory for municipal/potable
        "escalation_keywords": ["ultrapure water", "semiconductor water"],
        "typical_questions": [
            "Is this potable water (NSF 61 required) or process?",
            "Upstream of RO or final polish?",
            "Municipal, industrial, or boiler feed?",
            "What's the flow rate and micron target?",
        ],
        "notes": "NSF 61 MANDATORY for any potable water contact. 5-25 µm for RO pre-filtration. 0.5-5 µm for final polish. 0.2 µm for critical.",
    },

    "HVAC": {
        "preferred_manufacturers": ["AAF", "Koch", "3M"],
        "preferred_media": ["Glass Fiber", "Polypropylene", "Cellulose"],
        "preferred_product_types": ["Filter", "Air Filter", "Bag Filter"],
        "micron_range": (1, 100),  # MERV-based; micron less central for air
        "fallback_micron_range": (0.3, 200),
        "required_certs": ["MERV 13", "MERV 14", "HEPA"],
        "escalation_keywords": ["cleanroom class 100", "semiconductor fab air"],
        "typical_questions": [
            "What MERV rating do they need — 8, 13, 14, or HEPA?",
            "Data center, commercial building, or industrial?",
            "Pre-filter stage, final, or exhaust?",
            "What's the airflow volume (CFM) and face velocity?",
        ],
        "notes": "Data centers typically MERV 13-14 with pre + final stages. Paint booths use rough pre + fine final + exhaust stage.",
    },

    "Chemical Processing": {
        "preferred_manufacturers": ["Pall", "Graver", "Filtrox"],
        "preferred_media": ["PTFE", "316 Stainless Steel", "PVDF"],  # Aggressive chemical resistance
        "preferred_product_types": ["Filter Cartridge", "Filter Element", "Bag Filter"],
        "micron_range": (0.5, 25),
        "fallback_micron_range": (0.1, 100),
        "required_certs": [],
        "escalation_keywords": [
            "unknown chemical", "mixed solvents", "concentrated acid above 50%",
            "temperature above 400", "hydrogen fluoride", "chlorine gas",
        ],
        "typical_questions": [
            "What chemical(s) and what concentration?",
            "What's the operating temperature?",
            "Do you have an SDS I can reference?",
            "Any mixed chemicals in the stream?",
        ],
        "notes": "Match media to chemical. PTFE for aggressive, 316SS for high temp, PP only for mild service. Unknown chemicals → SDS request and engineering review.",
    },

    "Compressed Air": {
        "preferred_manufacturers": ["Pall", "SPX Flow", "Parker"],
        "preferred_media": ["Glass Fiber", "Polypropylene", "Activated Carbon"],
        "preferred_product_types": ["Filter Element", "Filter Cartridge", "Coalescer"],
        "micron_range": (0.01, 5),  # Tight for compressed air quality
        "fallback_micron_range": (0.001, 40),
        "required_certs": ["ISO 8573-1"],
        "escalation_keywords": ["breathing air", "medical air"],
        "typical_questions": [
            "What ISO 8573-1 class are they targeting?",
            "Particulate only, oil removal, or dew point control?",
            "Instrument air, process air, or breathing air?",
            "What's the flow rate and operating pressure?",
        ],
        "notes": "Instrument air typically ISO 8573-1 class 1.4.1. Coalescing required for oil removal. Desiccant for dew point control.",
    },

    "Industrial": {
        "preferred_manufacturers": [],  # Widest open bucket — don't narrow manufacturer
        "preferred_media": [],           # Let candidates come through unfiltered by media
        "preferred_product_types": ["Filter Cartridge", "Filter Element", "Filter", "Bag Filter", "Filter Housing"],
        "micron_range": (1, 100),        # Broad — cover general plant service
        "fallback_micron_range": (0.1, 500),
        "required_certs": [],
        "escalation_keywords": [],
        "typical_questions": [
            "What's the fluid or gas you're filtering?",
            "What's the flow rate and operating temperature?",
            "What micron rating do you need?",
            "Is there a specific particle or contaminant you're targeting?",
        ],
        "notes": "Default bucket when the use case is 'cooling water', 'process water', 'general plant' without more specificity. Start with 10-25 µm depth for bulk removal.",
    },
}


def get_filter_rules(application_bucket: str) -> FilterRules:
    """Return the filter rules for an application bucket, or empty dict if unknown."""
    return APPLICATION_FILTERS.get(application_bucket, {})


def list_buckets() -> list[str]:
    """Return the 9 application bucket names."""
    return list(APPLICATION_FILTERS.keys())
