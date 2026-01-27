import os
import json
import re
import time
from groq import Groq
from app.config import Config

class GroqStrategist:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.api_key = Config.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in configuration.")
        
        self.client = Groq(api_key=self.api_key)
        self.model = model 
        
        self.system_prompt = (
            "You are a Senior Quantitative Portfolio Manager (Hedge Fund). You trade with cold, calculated mathematical precision.\n"
            "YOUR GOAL: Maximize Sharpe Ratio. Minimize Drawdown. Quality > Quantity.\n"
            "\n"
            "--- MARKET PHYSICS (BIF ENGINE) ---\n"
            "1. REGIME AWARENESS (HURST EXPONENT): \n"
            "   - If Hurst > 0.55 (TRENDING): You are a Trend Follower. TRUST FRACTAL BREAKOUTS. Buy Strength. Sell Weakness.\n"
            "   - If Hurst < 0.45 (MEAN REVERSION): You are in Safety Mode. IGNORE Breakouts (Fakeouts likely). Wait for Extremes.\n"
            "   - If Hurst is 0.45-0.55 (RANDOM): CASH IS KING. Do not trade.\n"
            "2. SIGNAL QUALITY (ENTROPY):\n"
            "   - If Entropy > 0.90: MARKET IS NOISY. Reduce size or HOLD. Do not gamble.\n"
            "\n"
            "--- ENTRY RULES (THE GATE) ---\n"
            "You may ONLY enter if ONE of the following is true (AND confirmed by Gate 4):\n"
            "A. [SMC ORDER BLOCK]: Price is INSIDE a confirmed Order Block.\n"
            "B. [TREND BREAKOUT]: A validated Bill Williams Fractal Breakout + Confluence.\n"
            "\n"
            "CRITICAL: INDICATORS (RSI/MACD) ARE CONFIRMATIONS ONLY.\n"
            "NEVER trade solely because 'RSI is low'. There MUST be a Structural Reason (OB or Fractal Break).\n"
            "\n"
            "--- EXECUTION LOGIC ---\n"
            "- BUY: (Bullish Regime OR Bullish Catalyst) AND (Valid Structure [GATE 4 PASSED]).\n"
            "- SELL: (Bearish Regime OR Bearish Catalyst) AND (Valid Structure [GATE 4 PASSED]).\n"
            "- HOLD: No Setup, High Entropy, or Conflicting Signals.\n"
            "\n"
            "JSON OUTPUT FORMAT:\n"
            "{"
            "\"action\": \"BUY\"|\"SELL\"|\"HOLD\", "
            "\"confidence_score\": 0.0-1.0, "
            "\"reasoning\": \"REGIME: [Trend/Range]. STRUCTURE: [Fractal/OB]. CONFIRMATION: [Indicators]. DECISION: [Final].\""
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
        # Rule: Must have [INSIDE_ZONE (READY)] OR [GATE 4 PASSED] to trade
        # If neither is present, block the trade.
        has_smc = "INSIDE_ZONE (READY)" in market_data
        has_gate4 = "[GATE 4 PASSED]" in market_data
        
        if not has_smc and not has_gate4 and decision['action'] != "HOLD":
            print(f"[BLOCK] ZERO TRUST INTERVENTION: AI attempted to trade without valid Setup.")
            decision['action'] = "HOLD"
            decision['confidence_score'] = 0.0
            decision['reasoning_summary'] = f"[BLOCK] HARD OVERRIDE: Python Logic blocked trade. No Valid Gate 4 Trigger. AI Reasoning: {decision.get('reasoning_summary', 'Unknown')}"
            
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
