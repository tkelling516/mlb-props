import os
from dotenv import load_dotenv
import mlb_data
import analyzer

# Load environment variables
load_dotenv()

def get_api_provider():
    """Determine which API provider is available based on keys."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    elif os.getenv("GEMINI_API_KEY"):
        return "gemini"
    else:
        return "fallback"

def query_gemini(prompt, system_instruction):
    """Query Google Gemini API."""
    import google.generativeai as genai
    
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    # We use gemini-1.5-flash as it is fast and excellent for analytics
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_instruction
    )
    
    response = model.generate_content(prompt)
    return response.text

def query_anthropic(prompt, system_instruction):
    """Query Anthropic Claude API."""
    import anthropic
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # We use claude-3-5-sonnet-20241022 or fallback to latest
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1500,
        system=system_instruction,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return message.content[0].text

def query_fallback(prompt, system_instruction):
    """
    Fallback mathematical/rule-based responder when no API keys are available.
    Parses the context to generate logical betting summaries.
    """
    response = "🤖 **MLB Betting Bot (Fallback Mode - No API Key Found)**\n\n"
    response += "To enable natural conversations, please add a `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` to your `.env` file.\n\n"
    
    # Simple keyword parsing of user query to find relevant matches
    prompt_lower = prompt.lower()
    
    # Let's extract today's stats from the prompt context (which we inject)
    # We will search the prompt for keywords
    if "parlay" in prompt_lower or "recommendation" in prompt_lower:
        response += "### Today's Suggested Bets (Rule-Based):\n"
        response += "Here are the top mathematical correlations calculated from today's game details:\n\n"
        
        # We try to load today's actual data to print it
        try:
            games = mlb_data.get_today_games()
            all_game_details = []
            for g in games[:5]:
                det = mlb_data.get_game_details(g["game_id"])
                if det:
                    all_game_details.append(analyzer.get_game_matchups(det))
            parlays = analyzer.build_parlay_recommendations(all_game_details)
            
            if parlays:
                for p in parlays[:2]:
                    response += f"**{p['title']} ({p['confidence']} Confidence - Score: {p['score']})**\n"
                    response += f"Matchup: {p['game']}\n"
                    for leg in p["legs"]:
                        response += f"- Leg: {leg['market']} **{leg['direction']}** | *{leg['reason']}*\n"
                    response += f"Rationale: {p['rationale']}\n\n"
            else:
                response += "No high-scoring parlays found for today's slate yet. Check back once games are populated.\n"
        except Exception as e:
            response += f"Could not load parlay listings: {e}\n"
            
    elif "schedule" in prompt_lower or "games" in prompt_lower or "today" in prompt_lower:
        response += "### Today's Game Slate:\n"
        try:
            games = mlb_data.get_today_games()
            for g in games:
                response += f"- **{g['away_team']}** @ **{g['home_team']}** | Starters: {g['away_pitcher_name']} vs {g['home_pitcher_name']} ({g['status']})\n"
        except Exception as e:
            response += f"Could not load game schedule: {e}\n"
    else:
        response += "I can help you review today's games, matchups, and parlays.\n"
        response += "- Type **'games'** to see today's schedule.\n"
        response += "- Type **'parlay'** to see today's top parlay recommendations.\n"
        response += "\n*Please supply an API key in your `.env` file to chat freely and get deeper matchup breakdowns!*"
        
    return response

def get_system_prompt():
    """Return the sports betting analyst system prompt."""
    return """You are a professional Sports Betting Analyst and MLB Sabermetrics expert. Your goal is to help the user identify high-probability betting lines and correlated parlays for today's slate of Major League Baseball (MLB) games.

You have access to:
- Official MLB Stats API data (pitcher ERA, WHIP, K/9, walk rates, opponent batting average, and handedness splits).
- Baseball Savant / Statcast leaderboards (Expected metrics like xwOBA, expected batting average xBA, barrel rates, hard hit rates, and exit velocity).
- Historical streak signals and matchup scores (0 to 100 rating) showing batter success likelihood.

Guidelines:
1. Explain the analytical rationale behind all recommendations. Use specific stats (e.g. 'Wheeler has a 0.94 WHIP vs right-handers and a 31% Whiff rate on his slider, making this a prime matchup').
2. Emphasize correlated betting angles:
   - Pitcher strikeouts OVER + Opposing team total UNDER.
   - Hot batter hits/total bases OVER + Team runs total OVER.
3. Be transparent about risks (e.g. bullpen vulnerability, weather issues if known, small sample size splits).
4. Do not make up stats. If a stat is TBD or empty, mention that the data is limited.
5. Format your answers clearly using Markdown tables, bullet points, and bold text. Keep it premium, logical, and structured.
"""

def generate_chat_response(user_message, chat_history=[], selected_game_id=None):
    """
    Generate a response to the user's message.
    Injects context about today's games, current game selection, and parlay analysis.
    """
    provider = get_api_provider()
    
    # 1. Fetch Today's General Slate Context
    games = mlb_data.get_today_games()
    slate_context = "### Today's Schedule:\n"
    for g in games[:6]:
        slate_context += f"- Game {g['game_id']}: {g['away_team']} at {g['home_team']} | Starting Pitchers: {g['away_pitcher_name']} (Away) vs {g['home_pitcher_name']} (Home) | Status: {g['status']}\n"
    
    # 2. If a game is selected, fetch and inject detailed stats for that game
    game_context = ""
    if selected_game_id:
        try:
            det = mlb_data.get_game_details(selected_game_id)
            if det:
                analysis = analyzer.get_game_matchups(det)
                game_context = f"\n### Current Selected Game Context ({det['away_team']} @ {det['home_team']}):\n"
                
                # Add Pitcher stats
                away_p = analysis["away_pitcher_stats"]
                home_p = analysis["home_pitcher_stats"]
                if away_p:
                    game_context += f"- Away Pitcher {away_p['name']}: ERA {away_p['era']}, WHIP {away_p['whip']}, K/9 {away_p['strikeouts_per_9']}, Savant xwOBA against {away_p.get('savant', {}).get('xwoba_against', 'TBD')}\n"
                if home_p:
                    game_context += f"- Home Pitcher {home_p['name']}: ERA {home_p['era']}, WHIP {home_p['whip']}, K/9 {home_p['strikeouts_per_9']}, Savant xwOBA against {home_p.get('savant', {}).get('xwoba_against', 'TBD')}\n"
                
                # Add Top Hitters
                game_context += "- Top Hitter Matchups:\n"
                for h in analysis["hitter_matchups"]["away_vs_home_pitcher"][:3]:
                    game_context += f"  - (Away) {h['name']} ({h['position']}) vs {analysis['home_pitcher']}: Matchup Score {h['rating']} (OPS vs hand: {h['ops_vs_hand']}, xwOBA: {h['xwoba']})\n"
                for h in analysis["hitter_matchups"]["home_vs_away_pitcher"][:3]:
                    game_context += f"  - (Home) {h['name']} ({h['position']}) vs {analysis['away_pitcher']}: Matchup Score {h['rating']} (OPS vs hand: {h['ops_vs_hand']}, xwOBA: {h['xwoba']})\n"
        except Exception as e:
            game_context = f"\n(Could not load detailed context for selected game: {e})\n"
            
    # Assemble the full prompt with embedded context
    full_prompt = f"""
[CONTEXT]
{slate_context}
{game_context}
[END CONTEXT]

User Request: {user_message}

Review the context details, address the user's request, and present your analysis using sports betting terminology.
"""
    
    system_instruction = get_system_prompt()
    
    # 3. Route to the appropriate provider
    try:
        if provider == "anthropic":
            return query_anthropic(full_prompt, system_instruction)
        elif provider == "gemini":
            return query_gemini(full_prompt, system_instruction)
        else:
            return query_fallback(user_message, system_instruction)
    except Exception as e:
        return f"⚠️ **Error running AI Model ({provider})**: {e}\n\n*Check that your API key in the `.env` file is valid, or delete it to use the local fallback mode.*"
