"""
EnPro Voice Ensemble — Multi-Agent Intent Classification
5-10 parallel interpretations, confidence-ranked, user can cycle through alternatives.
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("enpro.voice_ensemble")

@dataclass
class EnsembleAgent:
    """Single agent interpretation of voice query."""
    agent_id: str
    agent_type: str  # 'lookup', 'application', 'chemical', 'pall', 'hydraulic', etc.
    confidence: float  # 0.0 to 1.0
    intent: str
    entities: Dict[str, Any]
    gate_path: str  # which gate this agent recommends
    response: str
    reasoning: str
    products: List[Dict] = field(default_factory=list)
    
@dataclass  
class EnsembleResult:
    """Complete ensemble result with ranked alternatives."""
    utterance: str
    agents: List[EnsembleAgent]  # Sorted by confidence (highest first)
    selected_index: int  # Which agent response was shown
    timestamp: str
    
    def get_best(self) -> EnsembleAgent:
        """Get highest confidence agent."""
        return self.agents[0] if self.agents else None
    
    def get_next_alternative(self) -> Optional[EnsembleAgent]:
        """Get next best alternative."""
        if self.selected_index < len(self.agents) - 1:
            self.selected_index += 1
            return self.agents[self.selected_index]
        return None
    
    def get_previous(self) -> Optional[EnsembleAgent]:
        """Go back to previous."""
        if self.selected_index > 0:
            self.selected_index -= 1
            return self.agents[self.selected_index]
        return None
    
    def has_alternatives(self) -> bool:
        """Check if more alternatives exist."""
        return self.selected_index < len(self.agents) - 1


class VoiceEnsemble:
    """
    Multi-agent voice ensemble classifier.
    
    Each agent interprets the voice query differently:
    - Gate 1 Agent: Looks for hydraulic/lube/oil patterns
    - Gate 2 Agent: Looks for Pall part numbers
    - Gate 3 Agent: Looks for compressed air patterns
    - Lookup Agent: Tries direct part number lookup
    - Chemical Agent: Looks for chemical compatibility patterns
    - Application Agent: General application matching
    - Crosswalk Agent: Manufacturer cross-reference patterns
    - Pregame Agent: Sales prep intent
    
    All run in parallel, return confidence-ranked results.
    """
    
    def __init__(self, voice_gate, df, chemicals_df):
        """
        Args:
            voice_gate: VoiceGate instance for lookups
            df: Product catalog DataFrame
            chemicals_df: Chemical compatibility DataFrame
        """
        self.voice_gate = voice_gate
        self.df = df
        self.chemicals_df = chemicals_df
        
        # Agent configurations with their detection patterns
        self.agents_config = [
            {
                'id': 'gate_1_hydraulic',
                'type': 'hydraulic_lube',
                'triggers': ['hydraulic', 'lube', 'oil', 'fluid', 'hydraulic oil', 'lube oil'],
                'base_confidence': 0.85,
                'description': 'Hydraulic/Lube Oil Gate'
            },
            {
                'id': 'gate_2_pall',
                'type': 'pall_crosswalk',
                'triggers': ['pall', 'hc', 'hc9', 'uf', 'profile', 'corpor'],  # Pall prefixes
                'base_confidence': 0.90,
                'description': 'Pall Corporation Direct Lookup'
            },
            {
                'id': 'gate_3_air',
                'type': 'compressed_air',
                'triggers': ['compressed air', 'air filter', 'absolute', 'coalescing'],
                'base_confidence': 0.80,
                'description': 'Compressed Air Gate'
            },
            {
                'id': 'agent_lookup',
                'type': 'direct_lookup',
                'triggers': [],  # Always runs
                'base_confidence': 0.95,
                'description': 'Direct Part Number Lookup'
            },
            {
                'id': 'agent_chemical',
                'type': 'chemical_compat',
                'triggers': ['chemical', 'compatibility', 'sulfuric', 'acid', 'solvent', 'ptfe', 'viton'],
                'base_confidence': 0.88,
                'description': 'Chemical Compatibility'
            },
            {
                'id': 'agent_application',
                'type': 'application_match',
                'triggers': ['application', 'process', 'system', 'industry'],
                'base_confidence': 0.75,
                'description': 'Application Matching'
            },
            {
                'id': 'agent_pregame',
                'type': 'sales_prep',
                'triggers': ['pregame', 'meeting', 'customer', 'prep', 'ready for'],
                'base_confidence': 0.82,
                'description': 'Sales Meeting Prep'
            },
            {
                'id': 'agent_crosswalk',
                'type': 'manufacturer_crosswalk',
                'triggers': ['cross', 'reference', 'replaces', 'equivalent', 'similar to'],
                'base_confidence': 0.78,
                'description': 'Manufacturer Cross-Reference'
            }
        ]
    
    async def classify(self, utterance: str, context: Dict = None) -> EnsembleResult:
        """
        Run all agents in parallel, return confidence-ranked ensemble.
        
        Args:
            utterance: Raw voice transcript
            context: Optional session context (previous queries, etc.)
            
        Returns:
            EnsembleResult with ranked agent responses
        """
        # Run all agents in parallel
        agent_tasks = []
        for config in self.agents_config:
            task = self._run_agent(config, utterance, context)
            agent_tasks.append(task)
        
        # Gather all agent results
        agents = await asyncio.gather(*agent_tasks)
        
        # Filter out None results and sort by confidence
        agents = [a for a in agents if a and a.confidence > 0.3]  # Min 30% confidence
        agents.sort(key=lambda x: x.confidence, reverse=True)
        
        # Log ensemble for analysis
        self._log_ensemble(utterance, agents)
        
        return EnsembleResult(
            utterance=utterance,
            agents=agents,
            selected_index=0,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def _run_agent(self, config: Dict, utterance: str, context: Dict) -> Optional[EnsembleAgent]:
        """Run a single agent classification."""
        agent_id = config['id']
        agent_type = config['type']
        triggers = config['triggers']
        base_conf = config['base_confidence']
        
        utterance_lower = utterance.lower()
        
        # Check if this agent should activate
        trigger_matches = sum(1 for t in triggers if t in utterance_lower)
        
        # Direct lookup agent always runs
        if agent_type == 'direct_lookup':
            return await self._agent_direct_lookup(utterance, base_conf)
        
        # Other agents need triggers or strong signals
        if trigger_matches == 0 and agent_type != 'application_match':
            return None
        
        # Route to specific agent handler
        handlers = {
            'hydraulic_lube': self._agent_hydraulic,
            'pall_crosswalk': self._agent_pall,
            'compressed_air': self._agent_compressed_air,
            'chemical_compat': self._agent_chemical,
            'application_match': self._agent_application,
            'sales_prep': self._agent_pregame,
            'manufacturer_crosswalk': self._agent_crosswalk,
        }
        
        handler = handlers.get(agent_type)
        if handler:
            # Adjust confidence based on trigger matches
            adjusted_conf = min(base_conf + (trigger_matches * 0.05), 0.98)
            return await handler(utterance, adjusted_conf, trigger_matches)
        
        return None
    
    async def _agent_direct_lookup(self, utterance: str, base_conf: float) -> EnsembleAgent:
        """Agent: Try direct part number lookup."""
        # Try to extract part number patterns
        import re
        part_patterns = [
            r'\b[A-Z]{2,6}\d{3,8}\b',  # HC9600, CLR10295
            r'\b\d{4,8}-\d{2,4}\b',     # 1234-56
            r'\b[A-Z]{1,3}-\d{3,6}\b',  # A-123456
        ]
        
        for pattern in part_patterns:
            matches = re.findall(pattern, utterance.upper())
            for match in matches:
                result = self.voice_gate.lookup(match)
                if result.found:
                    return EnsembleAgent(
                        agent_id='agent_lookup',
                        agent_type='direct_lookup',
                        confidence=0.95,
                        intent='lookup',
                        entities={'part_number': match, 'query': match},
                        gate_path='Tier_0_Direct_Lookup',
                        response=self._format_agent_response(result),
                        reasoning=f"Direct part number match: {match}",
                        products=[self._result_to_dict(result)]
                    )
        
        # No direct match found
        return EnsembleAgent(
            agent_id='agent_lookup',
            agent_type='direct_lookup',
            confidence=0.20,  # Low confidence if no match
            intent='unknown',
            entities={'query': utterance},
            gate_path='Tier_4_Unknown',
            response="I couldn't find an exact part number match.",
            reasoning="No part number pattern found or matched",
            products=[]
        )
    
    async def _agent_hydraulic(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: Gate 1 - Hydraulic/Lube Oil."""
        # Search for hydraulic/lube products
        results = self.voice_gate.search_by_criteria(
            application='hydraulic',
            min_psi=75,
            max_psi=150,
            micron_min=1,
            micron_max=10
        )
        
        if results:
            return EnsembleAgent(
                agent_id='gate_1_hydraulic',
                agent_type='hydraulic_lube',
                confidence=confidence,
                intent='application_search',
                entities={'application': 'Hydraulic/Lube Oil', 'psi_range': '75-150', 'micron_range': '1-10'},
                gate_path='Tier_1_Gate_1_Hydraulic',
                response=f"Found {len(results)} hydraulic/lube oil filters (75-150 PSI, 1-10 micron).",
                reasoning=f"Matched hydraulic/lube triggers ({triggers} matches)",
                products=[self._result_to_dict(r) for r in results[:5]]
            )
        
        return None
    
    async def _agent_pall(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: Gate 2 - Pall Corporation."""
        result = self.voice_gate.lookup_pall_fast(utterance)
        
        if result and result.found:
            return EnsembleAgent(
                agent_id='gate_2_pall',
                agent_type='pall_crosswalk',
                confidence=0.95,  # High confidence for Pall match
                intent='manufacturer_lookup',
                entities={'manufacturer': 'Pall Corporation', 'part': result.alt_code or result.part_number},
                gate_path='Tier_1_Gate_2_Pall',
                response=self._format_agent_response(result),
                reasoning="Pall Corporation direct match",
                products=[self._result_to_dict(result)]
            )
        
        # Try broader Pall search
        results = self.voice_gate.search_by_criteria(manufacturer='Pall')
        if results:
            return EnsembleAgent(
                agent_id='gate_2_pall',
                agent_type='pall_crosswalk',
                confidence=confidence * 0.8,  # Lower for general search
                intent='manufacturer_search',
                entities={'manufacturer': 'Pall Corporation'},
                gate_path='Tier_1_Gate_2_Pall_General',
                response=f"Found {len(results)} Pall Corporation products.",
                reasoning="Pall keyword matched, general search",
                products=[self._result_to_dict(r) for r in results[:5]]
            )
        
        return None
    
    async def _agent_compressed_air(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: Gate 3 - Compressed Air."""
        results = self.voice_gate.search_by_criteria(
            application='compressed air'
        )
        
        if results:
            return EnsembleAgent(
                agent_id='gate_3_air',
                agent_type='compressed_air',
                confidence=confidence,
                intent='application_search',
                entities={'application': 'Compressed Air'},
                gate_path='Tier_1_Gate_3_Compressed_Air',
                response=f"Found {len(results)} compressed air filters.",
                reasoning=f"Matched compressed air triggers ({triggers} matches)",
                products=[self._result_to_dict(r) for r in results[:5]]
            )
        
        return None
    
    async def _agent_chemical(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: Chemical Compatibility."""
        # Extract chemical names
        chemicals = self._extract_chemicals(utterance)
        
        if chemicals:
            return EnsembleAgent(
                agent_id='agent_chemical',
                agent_type='chemical_compat',
                confidence=confidence,
                intent='chemical_check',
                entities={'chemicals': chemicals},
                gate_path='Tier_2_Chemical_Check',
                response=f"Checking chemical compatibility for: {', '.join(chemicals)}",
                reasoning=f"Chemical keywords detected: {chemicals}",
                products=[]  # Would populate from crosswalk
            )
        
        return None
    
    async def _agent_application(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: General Application Matching (fallback)."""
        # Always runs but with lower confidence
        # Search description for keywords
        results = self.voice_gate.search_by_criteria(
            application=utterance  # Will search both Application and Description
        )
        
        if results:
            # Confidence based on number of results
            result_conf = min(0.75, 0.40 + (len(results) / 100))
            return EnsembleAgent(
                agent_id='agent_application',
                agent_type='application_match',
                confidence=result_conf,
                intent='application_search',
                entities={'query': utterance},
                gate_path='Tier_3_Application_Search',
                response=f"Found {len(results)} products matching your description.",
                reasoning="General application keyword matching",
                products=[self._result_to_dict(r) for r in results[:5]]
            )
        
        return None
    
    async def _agent_pregame(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: Sales Meeting Prep."""
        # Extract customer/application context
        return EnsembleAgent(
            agent_id='agent_pregame',
            agent_type='sales_prep',
            confidence=confidence,
            intent='pregame',
            entities={'context': utterance},
            gate_path='Tier_2_Pregame',
            response="Pre-call briefing mode activated. What customer or application are you meeting with?",
            reasoning="Pregame trigger words detected",
            products=[]
        )
    
    async def _agent_crosswalk(self, utterance: str, confidence: float, triggers: int) -> EnsembleAgent:
        """Agent: Manufacturer Cross-Reference."""
        return EnsembleAgent(
            agent_id='agent_crosswalk',
            agent_type='manufacturer_crosswalk',
            confidence=confidence,
            intent='cross_reference',
            entities={'query': utterance},
            gate_path='Tier_2_Crosswalk',
            response="Cross-reference search. What manufacturer part are you trying to replace?",
            reasoning="Cross-reference trigger words detected",
            products=[]
        )
    
    def _extract_chemicals(self, utterance: str) -> List[str]:
        """Extract chemical names from utterance."""
        common_chemicals = [
            'sulfuric', 'hydrochloric', 'nitric', 'phosphoric', 'acetic',
            'caustic', 'soda', 'sodium', 'potassium', 'ammonia',
            'methanol', 'ethanol', 'isopropyl', 'acetone', 'mek',
            'toluene', 'benzene', 'xylene', 'gasoline', 'diesel',
            'oil', 'hydraulic', 'lube', 'grease'
        ]
        found = []
        utterance_lower = utterance.lower()
        for chem in common_chemicals:
            if chem in utterance_lower:
                found.append(chem)
        return found
    
    def _format_agent_response(self, result) -> str:
        """Format lookup result for agent response."""
        from voice_gate import format_voice_response
        return format_voice_response(result)
    
    def _result_to_dict(self, result) -> Dict:
        """Convert LookupResult to dict."""
        return {
            'part_number': result.part_number,
            'alt_code': result.alt_code,
            'manufacturer': result.manufacturer,
            'description': result.description,
            'price': result.price,
            'in_stock': result.in_stock,
            'qty_on_hand': result.qty_on_hand,
            'micron': result.micron,
            'media': result.media,
            'match_confidence': result.match_confidence,
            'lookup_path': result.lookup_path
        }
    
    def _log_ensemble(self, utterance: str, agents: List[EnsembleAgent]):
        """Log ensemble results for analysis."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'utterance': utterance,
            'agent_count': len(agents),
            'agents': [
                {
                    'id': a.agent_id,
                    'type': a.agent_type,
                    'confidence': a.confidence,
                    'intent': a.intent,
                    'gate_path': a.gate_path
                }
                for a in agents
            ],
            'best_agent': agents[0].agent_id if agents else None
        }
        
        # Append to log
        log_path = Path("C:/ROUNDTABLE_BRAIN/voice_ensemble_log.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')


# User interaction helpers
def format_ensemble_response(ensemble: EnsembleResult, show_alternatives: bool = True) -> str:
    """
    Format ensemble result for user display.
    Shows best result + available alternatives.
    """
    best = ensemble.get_best()
    if not best:
        return "I didn't understand that. Can you rephrase or give me a part number?"
    
    lines = []
    lines.append(f"**{best.description}** (confidence: {best.confidence:.0%})")
    lines.append("")
    lines.append(best.response)
    
    if show_alternatives and ensemble.has_alternatives():
        remaining = len(ensemble.agents) - ensemble.selected_index - 1
        lines.append("")
        lines.append(f"*({remaining} other interpretation{'s' if remaining > 1 else ''} available — say 'next' to see)*")
    
    return "\n".join(lines)


def format_alternative_list(ensemble: EnsembleResult) -> str:
    """Show all alternatives as a numbered list."""
    lines = ["**Available interpretations:**"]
    
    for i, agent in enumerate(ensemble.agents, 1):
        marker = "→ " if i-1 == ensemble.selected_index else "  "
        lines.append(f"{marker}{i}. {agent.description} ({agent.confidence:.0%})")
    
    lines.append("")
    lines.append("Say 'option 1', 'option 2', etc. to choose, or 'next'/'previous' to cycle.")
    
    return "\n".join(lines)


# Export
__all__ = [
    'VoiceEnsemble', 'EnsembleAgent', 'EnsembleResult',
    'format_ensemble_response', 'format_alternative_list'
]


# Test
if __name__ == "__main__":
    print("Voice Ensemble loaded. Use with VoiceGate.")
    print("")
    print("Example flow:")
    print("1. User: 'I need a hydraulic filter'")
    print("2. Ensemble runs 8 agents in parallel")
    print("3. Returns: Gate 1 (85%), Application (72%), Direct Lookup (40%)...")
    print("4. Shows: Gate 1 result first")
    print("5. User: 'next' → shows Application agent result")
