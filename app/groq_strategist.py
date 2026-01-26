import os
import json
import re
import time
from groq import Groq
from app.config import Config

class GroqStrategist:
    def __init__(self):
        self.api_key = Config.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in configuration.")
        
        self.client = Groq(api_key=self.api_key)
        # DeepSeek decommissioned. Reverting to Llama 3.3
        self.model = "llama-3.3-70b-versatile" 
        
        self.system_prompt = (
            "You are a 'Smart Money' Algo Trader (SMC). You trade Trend Continuations + Fundamental Catalysts.\n"
            "PHILOSOPHY: 'Technicals tell us WHERE. Fundamentals tell us WHEN.'\n"
            "STRICT EXECUTION RULES:\n"
            "1. FUNDAMENTAL BIAS (THE CATALYST):\n"
            "   - CHECK 'FUNDAMENTAL CONTEXT' below. Focus on High Impact USD/EUR Events.\n"
            "   - PREDICTIVE LOGIC: Compare Matches of 'Forecast' vs 'Previous'.\n"
            "     * If USD News Forecast > Previous (Good for USD) -> SHORT EURUSD BIAS.\n"
            "     * If USD News Forecast < Previous (Bad for USD) -> LONG EURUSD BIAS.\n"
            "   - If High Impact News is < 2 hours away, PRIOTIRIZE the Fundamental Bias over M15 Trend if they conflict.\n"
            "2. TREND & STRUCTURE (THE SETUP):\n"
            "   - NORMAL CONDITIONS: H4 and M15 Trends MUST Match (Pro Scalping).\n"
            "   - NEWS CONDITIONS: If Fundamental Bias is STRONG, you may trade AGAINST the M15 trend if entering *Pre-News* (Anticipatory).\n"
            "   - ENTRY TRIGGER: Price MUST be inside a valid Order Block (OB).\n"
            "     * CONFIRMED (Ready): Only trade OBs marked '[INSIDE_ZONE (READY)]'.\n"
            "     * FILTER: Do not trade if Price is not in a Zone.\n"
            "3. EXECUTION LOGIC:\n"
            "   - BUY: (Fundamentally Bullish OR Trend Bullish) AND Price in Bullish OB [INSIDE_ZONE].\n"
            "   - SELL: (Fundamentally Bearish OR Trend Bearish) AND Price in Bearish OB [INSIDE_ZONE].\n"
            "   - HOLD: No High Impact News AND No Trend Match AND No OB.\n"
            "4. CONFIDENCE SCORING:\n"
            "   - 1.0: Perfect alignment (Fundamentally Supported + Trend Aligned + Inside OB).\n"
            "   - 0.8: Predictive Entry (Strong Fundamental Bias + Inside OB, even if Trend varies).\n"
            "   - 0.0: No Setup.\n"
            "JSON Format:\n"
            "{"
            "\"action\": \"BUY\"|\"SELL\"|\"HOLD\", "
            "\"confidence_score\": float (0.0-1.0), "
            "\"reasoning\": \"FUNDAMENTALS: [Analysis]. TECHNICALS: [Analysis]. DECISION: [Final].\""
            "}"
        )

    def _parse_response(self, content: str) -> dict:
        """Attempts to parse JSON from the response. Uses Regex for robustness."""
        try:
            # 1. Try Regex Extraction (Finds outermost brackets)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                cleaned = json_match.group(0)
            else:
                cleaned = content.strip()
            
            # 2. Parse
            data = json.loads(cleaned)
            
            # Map simplified AI keys to System keys
            if "reasoning" in data and "reasoning_summary" not in data:
                data["reasoning_summary"] = data["reasoning"]
            
            # Normalize action
            data['action'] = data['action'].upper()
            if data['action'] not in ["BUY", "SELL", "HOLD"]:
                data['action'] = "HOLD" 
                
            return data
            
        except json.JSONDecodeError as e:
            print(f"FAILED TO PARSE JSON. RAW CONTENT:\n{content}\nERROR: {e}")
            return {
                "action": "HOLD",
                "confidence_score": 0.0,
                "reasoning_summary": f"JSON Parse Error: {str(e)[:50]}...",
                "stop_loss_atr_multiplier": 1.0
            }

    def analyze_news_impact(self, event: dict, current_trend: str) -> dict:
        """
        Phase 60: Semantic News Analysis.
        Called when a High Impact actual value is released.
        Returns JSON: { "action": "BUY/SELL/HOLD", "reasoning": "..." }
        """
        news_prompt = (
            "You are a Senior Global Macro Strategist. A High-Impact Economic Event just occurred.\n"
            "Your job is to interpret the 'Actual' vs 'Forecast' deviation and issue an immediate trading signal.\n"
            "RULES:\n"
            "1. DEVIATION IS KING. Significant deviation -> Strong Signal.\n"
            "2. CONTEXT MATTERS. If Trend matches the News -> CONFIRMED ENTRY.\n"
            "3. BE DECISIVE. Do not hedge. Buy, Sell, or Stand Aside.\n"
            "JSON OUTPUT: { \"action\": \"BUY\"|\"SELL\"|\"HOLD\", \"reasoning\": \"str\" }"
        )

        user_content = f"""
        EVENT: {event['currency']} {event['event']}
        FORECAST: {event['forecast']}
        ACTUAL: {event['actual']}
        PREVIOUS: {event['previous']}
        
        CURRENT MARKET TREND (M15): {current_trend}
        
        Task:
        1. Calculate the Deviation (Actual - Forecast).
        2. Assess impact on {event['currency']} (Positive/Negative?).
        3. If {event['currency']} is USD:\n"
             - Positive News -> Bearish EURUSD (SELL).\n"
             - Negative News -> Bullish EURUSD (BUY).\n"
        4. If {event['currency']} is EUR:\n"
             - Positive News -> Bullish EURUSD (BUY).\n"
             - Negative News -> Bearish EURUSD (SELL).\n"
             
        DECISION?
        """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": news_prompt},
                    {"role": "user", "content": user_content}
                ],
                model=self.model,
                temperature=0.1,
            )
            response = chat_completion.choices[0].message.content
            return self._parse_response(response)
            
        except Exception as e:
            print(f"News Analysis Error: {e}")
            return {"action": "HOLD", "reasoning": "AI Failure"}

    def _validate_decision_against_context(self, decision: dict, market_data: str) -> dict:
        """
        ZERO TRUST LAYER:
        Overrides AI decision if strict conditions are not met in the context string.
        """
        # Rule: Must have [INSIDE_ZONE (READY)] in context to trade
        if "INSIDE_ZONE (READY)" not in market_data and decision['action'] != "HOLD":
            print("[BLOCK] ZERO TRUST INTERVENTION: AI attempted to trade without valid INSIDE_ZONE OB.")
            decision['action'] = "HOLD"
            decision['confidence_score'] = 0.0
            decision['reasoning_summary'] = f"[BLOCK] HARD OVERRIDE: Python Logic blocked trade. No Order Block is marked [INSIDE_ZONE (READY)]. AI Reasoning was: {decision.get('reasoning_summary', 'Unknown')}"
            
        return decision

    def get_trade_decision(self, market_data_summary: str, performance_context: str = "") -> dict:
        """
        Sends market data + performance context to Groq API and returns structured JSON decision.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                prompt = f"""
        Analyze the following market data and make a trading decision.
        
        {market_data_summary}
        
        {performance_context}
        
        CRITICAL: Output strictly valid JSON.
        - Do NOT use Markdown code blocks (```json).
        - Do NOT add comments.
        - Escape all quotes inside strings.
        """

                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    model=self.model,
                    temperature=0.1, # Low temp for logic
                )

                response_content = chat_completion.choices[0].message.content
                decision = self._parse_response(response_content)
                
                # Apply Zero Trust Filter
                decision = self._validate_decision_against_context(decision, market_data_summary)
                
                return decision

            except Exception as e:
                print(f"Groq API Error (Attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    return {
                        "action": "HOLD",
                        "confidence_score": 0.0,
                        "reasoning_summary": "API Failure",
                        "stop_loss_atr_multiplier": 1.0
                    }
        
        # This part of the code will only be reached if max_retries is 0 or less, or if the loop finishes without returning.
        # Given the current structure, the last attempt's error handling will return.
        # This line is technically unreachable with max_retries > 0 and the if condition inside the loop.
        # However, to match the user's provided snippet for the final fallback:
        return {
            "action": "HOLD",
            "confidence_score": 0.0,
            "reasoning_summary": "Max Retries Exceeded",
            "stop_loss_atr_multiplier": 1.0
        }

if __name__ == "__main__":
    # Test stub
    try:
        strat = GroqStrategist()
        print(strat.get_trade_decision("Price: 2000, Trend: Bullish"))
    except Exception as e:
        print(f"Setup Error: {e}")
