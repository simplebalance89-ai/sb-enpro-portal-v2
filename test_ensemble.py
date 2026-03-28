"""
Test script for Voice Ensemble.
Shows the multi-agent approach in action.
"""

import asyncio
import sys
sys.path.insert(0, 'C:/Claude/Repos/enpro-fm-portal')

from voice_gate import VoiceGate, LookupResult
from voice_ensemble import VoiceEnsemble, format_ensemble_response, format_alternative_list

# Mock test — simulates ensemble without full data
async def demo_ensemble():
    """Demo the ensemble concept with mock agents."""
    
    print("=" * 70)
    print("ENPRO VOICE ENSEMBLE DEMO")
    print("=" * 70)
    print()
    print("Simulating: 'I need a hydraulic filter for 100 PSI system'")
    print()
    
    # Mock agents responding to this query
    from voice_ensemble import EnsembleAgent
    
    agents = [
        EnsembleAgent(
            agent_id="gate_1_hydraulic",
            agent_type="hydraulic_lube",
            confidence=0.92,
            intent="application_search",
            entities={"application": "Hydraulic Oil", "psi": "100"},
            gate_path="Tier_1_Gate_1_Hydraulic",
            response="Found 47 hydraulic oil filters rated for 100 PSI with 1-10 micron.",
            reasoning="Matched 'hydraulic' (95%), '100 PSI' (95%), 'filter' (90%) — highest confidence for this gate",
            products=[
                {"alt_code": "CLR12345", "description": "Hydraulic Filter 100 PSI", "price": 45.99},
                {"alt_code": "CLR12346", "description": "Hydraulic Filter 150 PSI", "price": 52.99},
            ]
        ),
        EnsembleAgent(
            agent_id="agent_chemical",
            agent_type="chemical_compat",
            confidence=0.45,
            intent="chemical_check",
            entities={"chemicals": []},
            gate_path="Tier_2_Chemical_Check",
            response="No specific chemicals mentioned. General hydraulic oil compatibility available.",
            reasoning="No chemical keywords detected, but hydraulic implies oil compatibility",
            products=[]
        ),
        EnsembleAgent(
            agent_id="agent_application",
            agent_type="application_match",
            confidence=0.38,
            intent="keyword_search",
            entities={"keywords": ["hydraulic", "filter", "100"]},
            gate_path="Tier_3_Application_Search",
            response="Found 12 products with 'hydraulic filter' in description.",
            reasoning="General keyword matching — lower confidence than specific gate match",
            products=[]
        ),
        EnsembleAgent(
            agent_id="agent_crosswalk",
            agent_type="manufacturer_crosswalk",
            confidence=0.25,
            intent="cross_reference",
            entities={},
            gate_path="Tier_2_Crosswalk",
            response="No manufacturer cross-reference requested.",
            reasoning="No 'replaces' or 'equivalent' keywords",
            products=[]
        ),
    ]
    
    # Map agent_type to description
    descriptions = {
        "hydraulic_lube": "Gate 1: Hydraulic/Lube Oil",
        "chemical_compat": "Agent: Chemical Compatibility",
        "application_match": "Agent: Application Matching",
        "manufacturer_crosswalk": "Agent: Manufacturer Cross-Reference",
    }
    
    from voice_ensemble import EnsembleResult
    
    ensemble = EnsembleResult(
        utterance="I need a hydraulic filter for 100 PSI system",
        agents=agents,
        selected_index=0,
        timestamp="2026-03-28T15:30:00Z"
    )
    
    # Show the result
    print("=" * 70)
    print("ENSEMBLE RESULTS (4 agents responded)")
    print("=" * 70)
    print()
    
    for i, agent in enumerate(ensemble.agents, 1):
        marker = "→ " if i == 1 else "  "
        desc = descriptions.get(agent.agent_type, agent.agent_type)
        print(f"{marker}{i}. {desc}")
        print(f"     Confidence: {agent.confidence:.0%} | Intent: {agent.intent}")
        print(f"     Gate: {agent.gate_path}")
        print()
    
    print("=" * 70)
    print("USER SEES (best result):")
    print("=" * 70)
    print()
    print(format_ensemble_response(ensemble))
    print()
    
    # Simulate user asking for next option
    print("=" * 70)
    print("USER: 'next'")
    print("=" * 70)
    print()
    
    ensemble.get_next_alternative()
    print(format_ensemble_response(ensemble))
    print()
    
    # Show all options
    print("=" * 70)
    print("USER: 'show all'")
    print("=" * 70)
    print()
    print(format_alternative_list(ensemble))
    print()
    
    print("=" * 70)
    print("HOW IT WORKS")
    print("=" * 70)
    print("""
1. User speaks query
2. 5-10 parallel agents interpret:
   • Gate 1: Hydraulic patterns → 92% confidence
   • Gate 2: Pall lookup → 0% (no match)
   • Gate 3: Compressed air → 0% (no match)
   • Agent 4: Chemical check → 45% (hydraulic oil implied)
   • Agent 5: Application match → 38% (general keywords)
   • Agent 6: Pregame → 0% (no prep words)
   • Agent 7: Direct lookup → 0% (no part number)
   • Agent 8: Crosswalk → 25% (weak signal)
   
3. Sort by confidence: [92%, 45%, 38%, 25%]
4. Show best: Gate 1 Hydraulic
5. User can say 'next' to see chemical compatibility view

This is Voice Crowdsource — multiple agents vote, best wins.
""")


async def demo_with_live_gate():
    """Demo with actual voice gate if data available."""
    from pathlib import Path
    
    data_path = None
    for candidate in [
        Path("C:/ROUNDTABLE_BRAIN/filtration_products.csv"),
        Path("./filtration_products.csv"),
    ]:
        if candidate.exists():
            data_path = str(candidate)
            break
    
    if not data_path:
        print("No data file found — running mock demo only.")
        return
    
    print("=" * 70)
    print("LIVE ENSEMBLE DEMO")
    print("=" * 70)
    print(f"Data: {data_path}")
    print()
    
    # Load gate
    gate = VoiceGate(data_path)
    
    # Test queries
    test_queries = [
        "Find me a 5 micron hydraulic filter",
        "I need something for compressed air",
        "Pall HC9600",
        "Ready for my meeting with Acme Corp",
        "Cross reference Parker part 12345",
    ]
    
    for query in test_queries:
        print(f"Query: '{query}'")
        print("-" * 50)
        
        # Run ensemble
        ensemble = VoiceEnsemble(gate, gate.df, None)
        result = await ensemble.classify(query)
        
        print(f"Agents responded: {len(result.agents)}")
        for agent in result.agents[:3]:
            print(f"  • {agent.description}: {agent.confidence:.0%} → {agent.gate_path}")
        print()


if __name__ == "__main__":
    # Always run mock demo
    asyncio.run(demo_ensemble())
    
    # Try live if possible
    print("\n" + "=" * 70)
    try:
        asyncio.run(demo_with_live_gate())
    except Exception as e:
        print(f"Live demo skipped: {e}")
