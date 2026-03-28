"""
EnPro Voice Interface — Ensemble-Powered Voice Search
Main entry point for voice queries.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from voice_gate import VoiceGate, LookupResult
from voice_ensemble import VoiceEnsemble, EnsembleResult, format_ensemble_response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enpro.voice_interface")


class EnProVoiceInterface:
    """
    Main voice interface for EnPro filtration search.
    
    Uses ensemble approach:
    1. User speaks query
    2. 5-10 agents interpret in parallel
    3. Highest confidence result shown
    4. User can request alternatives
    
    Simple commands:
    - "next" / "previous" — cycle through alternatives
    - "option 1" / "option 2" — jump to specific agent
    - "show all" — list all interpretations
    - "details" — more info on current result
    """
    
    def __init__(self, data_path: str = None):
        """
        Initialize voice interface.
        
        Args:
            data_path: Path to filtration CSV data
        """
        self.gate = VoiceGate(data_path)
        self.ensemble = VoiceEnsemble(
            voice_gate=self.gate,
            df=self.gate.df,
            chemicals_df=getattr(self.gate, 'chemicals_df', None)
        )
        
        # Session state
        self.current_ensemble: Optional[EnsembleResult] = None
        self.session_history = []
        
        logger.info("EnPro Voice Interface initialized")
    
    async def query(self, utterance: str, context: dict = None) -> str:
        """
        Process voice query and return response.
        
        Args:
            utterance: Raw voice transcript
            context: Optional session context
            
        Returns:
            Formatted response string
        """
        utterance_lower = utterance.lower().strip()
        
        # Handle navigation commands
        if self._is_navigation_command(utterance_lower):
            return self._handle_navigation(utterance_lower)
        
        # New query — run ensemble
        logger.info(f"Processing query: {utterance}")
        
        try:
            self.current_ensemble = await self.ensemble.classify(
                utterance=utterance,
                context=context or {}
            )
            
            # Log to session
            self.session_history.append({
                'query': utterance,
                'best_agent': self.current_ensemble.agents[0].agent_id if self.current_ensemble.agents else None,
                'confidence': self.current_ensemble.agents[0].confidence if self.current_ensemble.agents else 0
            })
            
            # Return formatted response
            return format_ensemble_response(self.current_ensemble)
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return f"Sorry, I had trouble processing that. Error: {str(e)}"
    
    def _is_navigation_command(self, utterance: str) -> bool:
        """Check if utterance is a navigation command."""
        nav_commands = [
            'next', 'previous', 'back', 'last',
            'option 1', 'option 2', 'option 3', 'option 4', 'option 5',
            'option 6', 'option 7', 'option 8', 'option 9', 'option 10',
            'show all', 'list all', 'all options',
            'details', 'more info', 'tell me more',
            'start over', 'reset', 'new search'
        ]
        return any(cmd in utterance for cmd in nav_commands)
    
    def _handle_navigation(self, utterance: str) -> str:
        """Handle navigation commands."""
        if not self.current_ensemble:
            return "No active query. What are you looking for?"
        
        # Next / Previous
        if 'next' in utterance:
            agent = self.current_ensemble.get_next_alternative()
            if agent:
                return format_ensemble_response(self.current_ensemble, show_alternatives=True)
            return "That's the last option. Say 'previous' to go back or ask something new."
        
        if 'previous' in utterance or 'back' in utterance:
            agent = self.current_ensemble.get_previous()
            if agent:
                return format_ensemble_response(self.current_ensemble, show_alternatives=True)
            return "That's the first option. Say 'next' to see alternatives."
        
        # Option N
        for i in range(1, 11):
            if f'option {i}' in utterance or f'number {i}' in utterance:
                if i <= len(self.current_ensemble.agents):
                    self.current_ensemble.selected_index = i - 1
                    return format_ensemble_response(self.current_ensemble, show_alternatives=True)
                return f"Only {len(self.current_ensemble.agents)} options available."
        
        # Show all
        if 'show all' in utterance or 'list all' in utterance or 'all options' in utterance:
            from voice_ensemble import format_alternative_list
            return format_alternative_list(self.current_ensemble)
        
        # Details
        if 'details' in utterance or 'more info' in utterance:
            return self._format_detailed_response()
        
        # Start over
        if 'start over' in utterance or 'reset' in utterance or 'new search' in utterance:
            self.current_ensemble = None
            return "OK, what are you looking for?"
        
        return "I'm not sure what you want. Say 'next', 'previous', or 'show all'."
    
    def _format_detailed_response(self) -> str:
        """Format detailed response for current selection."""
        agent = self.current_ensemble.agents[self.current_ensemble.selected_index]
        
        lines = [
            f"**{agent.description}**",
            f"Confidence: {agent.confidence:.0%}",
            f"Intent: {agent.intent}",
            f"Gate Path: {agent.gate_path}",
            "",
            f"Response: {agent.response}",
            "",
            "**Reasoning:**",
            agent.reasoning
        ]
        
        if agent.products:
            lines.extend([
                "",
                f"**Products ({len(agent.products)} shown):**",
            ])
            for i, p in enumerate(agent.products[:5], 1):
                lines.append(f"{i}. {p.get('alt_code', 'N/A')} - {p.get('description', 'N/A')[:50]}...")
        
        return "\n".join(lines)
    
    def get_session_summary(self) -> str:
        """Get summary of current session."""
        if not self.session_history:
            return "No queries yet."
        
        lines = [f"**Session Summary ({len(self.session_history)} queries)**", ""]
        for i, entry in enumerate(self.session_history[-5:], 1):
            lines.append(f"{i}. {entry['query'][:40]}... → {entry['best_agent']} ({entry['confidence']:.0%})")
        
        return "\n".join(lines)


# Simple CLI demo
async def run_demo():
    """Run interactive voice demo."""
    print("=" * 60)
    print("EnPro Voice Ensemble Demo")
    print("=" * 60)
    print()
    print("Try these queries:")
    print("  • 'I need a hydraulic filter for 100 PSI'")
    print("  • 'Find me a Pall HC9600 equivalent'")
    print("  • 'Compressed air filter absolute rating'")
    print("  • 'Ready for meeting with Acme Corp'")
    print()
    print("Navigation: 'next', 'previous', 'option 1', 'show all', 'details'")
    print("Type 'quit' to exit")
    print("-" * 60)
    print()
    
    # Find data file
    data_path = None
    for candidate in [
        Path("C:/ROUNDTABLE_BRAIN/filtration_products.csv"),
        Path("./filtration_products.csv"),
        Path("../filtration_products.csv"),
    ]:
        if candidate.exists():
            data_path = str(candidate)
            break
    
    interface = EnProVoiceInterface(data_path)
    
    while True:
        try:
            user_input = input("\n🎤 ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                continue
            
            print()
            response = await interface.query(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(run_demo())
