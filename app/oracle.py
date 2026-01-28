import logging
from datetime import datetime
from app.groq_strategist import GroqStrategist

class Oracle:
    """
    Phase 90: The Oracle.
    Generates Narrative Intelligence for the Human Operator.
    Explains 'WHY' the swarm is doing what it's doing.
    """
    def __init__(self, strategist: GroqStrategist):
        self.ai = strategist
        self.last_brief = "System initializing..."
        self.last_update = None
        
    def generate_brief(self, market_data: dict, regime: dict, leader_name: str, active_trades: list) -> str:
        """
        Synthesizes a 3-sentence 'Morning Brief' style update.
        """
        # 1. Rate Limit (Don't spam LLM every tick, only every 15 mins or on major change)
        if self.last_update:
            seconds_since = (datetime.now() - self.last_update).total_seconds()
            if seconds_since < 900: # 15 minutes
                return self.last_brief
                
        # 2. Construct Prompt
        context = f"""
        Market Regime: {regime.get('trend', 'UNKNOWN')} ({regime.get('summary', '')})
        Current Alpha Strategy: {leader_name}
        Active Trades: {len(active_trades)}
        Recent Price Action: {market_data.get('close', 'N/A')}
        """
        
        prompt = f"""
        You are 'The Oracle', an AI Market Analyst for a hedge fund.
        Write a very short, punchy, professional update (max 40 words) for the dashboard.
        Focus on the 'Why'.
        
        Context:
        {context}
        
        Output format: Just the text. No preamble.
        Example: "Bullish momentum confirmed by H1 breakout. Swarm is accumulating Longs via TrendHawk. News risk is low."
        """
        
        try:
            narrative = self.ai.get_narrative_intelligence(prompt)
            self.last_brief = narrative
            self.last_update = datetime.now()
            return narrative
            
        except Exception as e:
            logging.error(f"Oracle Error: {e}")
            return self.last_brief
