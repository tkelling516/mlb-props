import os
import importlib
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import mlb_data
import analyzer
import agent

# Force reload local modules during development to avoid cached imports
importlib.reload(mlb_data)
importlib.reload(analyzer)
importlib.reload(agent)

# Start automated scheduler background thread
@st.cache_resource
def start_scheduler_thread():
    import threading
    import time
    
    def scheduler_loop():
        print("[Scheduler Thread] Starting background hourly scheduler loop...")
        # Run catch-up check asynchronously in the background thread at startup
        try:
            analyzer.catch_up_tracker_jobs()
        except Exception as e:
            print(f"Startup scheduler catch-up error: {e}")
            
        while True:
            # Sleep for 1 hour (3600 seconds)
            time.sleep(3600)
            try:
                analyzer.catch_up_tracker_jobs()
            except Exception as e:
                print(f"Background scheduler thread error: {e}")
                
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    return t

# Trigger thread startup once
start_scheduler_thread()

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="⚾ MLB BET AI | Betting Analytics & Parlay Agent",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Glassmorphic Light-Mode CSS styling (High Readability)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* Global Styles */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: 'Outfit', sans-serif;
    }
    
    /* Header Card */
    .header-card {
        background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.05);
    }
    
    .header-title {
        font-weight: 800;
        background: linear-gradient(to right, #1e3a8a, #2563eb, #6d28d9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .header-subtitle {
        color: #475569;
        font-size: 1.1rem;
        margin-top: 0.5rem;
        font-weight: 300;
    }
    
    /* Card Panel */
    .glass-card {
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(12px);
        border-radius: 12px;
        border: 1px solid rgba(15, 23, 42, 0.08);
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.04);
        transition: transform 0.2s, border-color 0.2s;
    }
    
    .glass-card:hover {
        border-color: rgba(37, 99, 235, 0.3);
        transform: translateY(-2px);
    }
    
    /* Selected Game Card */
    .glass-card-selected {
        background: rgba(37, 99, 235, 0.06);
        backdrop-filter: blur(12px);
        border-radius: 12px;
        border: 1px solid rgba(37, 99, 235, 0.4);
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 25px 0 rgba(37, 99, 235, 0.1);
    }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-high {
        background-color: rgba(16, 185, 129, 0.15);
        color: #065f46;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-medium {
        background-color: rgba(245, 158, 11, 0.15);
        color: #92400e;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-low {
        background-color: rgba(239, 68, 68, 0.15);
        color: #991b1b;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-blue {
        background-color: rgba(59, 130, 246, 0.15);
        color: #1e40af;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #f1f5f9 !important;
        border-right: 1px solid rgba(15, 23, 42, 0.08);
    }
    
    /* Scrollbars */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f8fafc;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(15, 23, 42, 0.1);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(37, 99, 235, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State Variables
if "selected_game" not in st.session_state:
    st.session_state.selected_game = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "date_str" not in st.session_state:
    st.session_state.date_str = datetime.today().strftime('%Y-%m-%d')

# Helper to save credentials to .env file
def save_api_keys(gemini_key, anthropic_key):
    lines = []
    if gemini_key:
        lines.append(f"GEMINI_API_KEY={gemini_key.strip()}\n")
    if anthropic_key:
        lines.append(f"ANTHROPIC_API_KEY={anthropic_key.strip()}\n")
        
    with open(".env", "w") as f:
        f.writelines(lines)
        
    # Reload environment in current process
    os.environ["GEMINI_API_KEY"] = gemini_key.strip()
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key.strip()
    st.success("API Keys updated successfully!")

# HEADER CARD
st.markdown("""
<div class="header-card">
    <h1 class="header-title">⚾ MLB PROP ANALYTICS & PARLAY AI</h1>
    <p class="header-subtitle">Find high-probability matchups, trace pitching splits, and generate correlated betting parlays powered by Statcast & AI</p>
</div>
""", unsafe_allow_html=True)

# SIDEBAR: API Settings & Systems Control
with st.sidebar:
    st.markdown("### ⚙️ SETTINGS & CONTROLS")
    
    # API Credentials Expandable panel
    with st.expander("🔑 API Key Configuration", expanded=False):
        gemini_api_key = st.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
        anthropic_api_key = st.text_input("Claude API Key", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password")
        if st.button("Save Keys", use_container_width=True):
            save_api_keys(gemini_api_key, anthropic_api_key)
            
    # System Status Panel
    st.markdown("---")
    st.markdown("### 🛰️ SYSTEM STATUS")
    provider = agent.get_api_provider()
    
    if provider == "gemini":
        st.markdown("🟢 **Model**: Gemini (1.5 Flash)")
    elif provider == "anthropic":
        st.markdown("🟢 **Model**: Claude (3.5 Sonnet)")
    else:
        st.markdown("🟡 **Model**: Fallback (Rule-Based Mode)")
        st.caption("Add an API key above to enable conversational AI analysis.")

    # Date selector
    st.markdown("---")
    date_val = st.date_input("Slate Date", value=datetime.today())
    date_selected_str = date_val.strftime('%Y-%m-%d')
    if date_selected_str != st.session_state.date_str:
        st.session_state.date_str = date_selected_str
        st.session_state.selected_game = None
        # Invalidate cache memory on page change
        st.rerun()

    # Clear Cache
    st.markdown("---")
    if st.button("🔄 Force Refresh Data", use_container_width=True):
        cache_files = [
            os.path.join("cache", f"{st.session_state.date_str}_games.json"),
        ]
        # Clear selected game file as well if any
        if st.session_state.selected_game:
            cache_files.append(os.path.join("cache", f"{st.session_state.date_str}_game_{st.session_state.selected_game}.json"))
            
        for f in cache_files:
            if os.path.exists(f):
                os.remove(f)
        st.session_state.selected_game = None
        st.toast("Cache cleared. Re-fetching data...")
        st.rerun()

# DATA LOADING PIPELINE
with st.spinner("Retrieving MLB game rosters, season splits, and Savant leaderboards..."):
    # This fetches and caches data automatically
    games_slate = mlb_data.get_today_games(st.session_state.date_str)
    
    # Pre-load raw game details once to share between tabs (speeding up page reload)
    full_slate_raw_details = []
    for g in games_slate:
        det = mlb_data.get_game_details(g["game_id"], st.session_state.date_str)
        if det:
            full_slate_raw_details.append(det)
            
    # Pre-calculate game matchups
    full_slate_matchups = [analyzer.get_game_matchups(det) for det in full_slate_raw_details if det]

# ----------------- TABS CORE LAYOUT -----------------
tab_slate, tab_leaderboards, tab_parlays, tab_agent, tab_tracker, tab_strategy = st.tabs([
    "⚾ Today's Matchups", 
    "🎯 Player Prop Targets",
    "📈 Correlated Parlay Suggestions", 
    "💬 AI Bettor Chatbot",
    "📊 Results Tracker",
    "📉 Under Regression Strategy"
])

# ----------------- TAB 1: TODAY'S SLATE -----------------
with tab_slate:
    if not games_slate:
        st.info("No games scheduled for the selected date.")
    else:
        col_list, col_details = st.columns([1, 2])
        
        # COLUMN 1: GAMES LIST SELECTOR
        with col_list:
            st.markdown("### 🏟️ Today's Games")
            
            for game in games_slate:
                game_id = game["game_id"]
                away = game["away_team"]
                home = game["home_team"]
                away_p = game["away_pitcher_name"]
                home_p = game["home_pitcher_name"]
                status = game["status"]
                
                # Render differently if selected
                is_selected = st.session_state.selected_game == game_id
                card_class = "glass-card-selected" if is_selected else "glass-card"
                
                score_str = f"({game['away_runs']} - {game['home_runs']})" if status in ["In Progress", "Final"] else ""
                
                card_html = f"""
                <div class="{card_class}">
                    <div style="display:flex; justify-content:space-between; font-weight:600; font-size:1.1rem; color:#0f172a;">
                        <span>{away} @ {home}</span>
                        <span style="color:#2563eb;">{score_str}</span>
                    </div>
                    <div style="font-size:0.85rem; color:#475569; margin-top:0.4rem;">
                        <div>Away: ⚾ {away_p}</div>
                        <div>Home: ⚾ {home_p}</div>
                    </div>
                    <div style="margin-top:0.6rem; display:flex; justify-content:space-between; align-items:center;">
                        <span class="badge badge-blue">{status}</span>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Streamlit button overlay to select game
                if st.button("Analyze Matchups", key=f"sel_{game_id}", use_container_width=True):
                    st.session_state.selected_game = game_id
                    st.rerun()
                    
        # COLUMN 2: DETAILED MATCHUP REPORT
        with col_details:
            if not st.session_state.selected_game:
                st.markdown("""
                <div class="glass-card" style="text-align:center; padding:5rem; color:#94a3b8;">
                    <h3>👈 Select a game from the slate to view detailed matchups</h3>
                    <p style="font-weight:300;">Includes pitcher vs. batter ratings, platoon splits, and Statcast metrics comparison.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Load selected game data details
                with st.spinner("Compiling player matchup matrices..."):
                    game_details = mlb_data.get_game_details(st.session_state.selected_game, st.session_state.date_str)
                    game_analysis = analyzer.get_game_matchups(game_details)
                    
                if not game_analysis:
                    st.error("Failed to load details for this matchup.")
                else:
                    st.markdown(f"## 🏟️ Matchup: {game_analysis['away_team']} @ {game_analysis['home_team']}")
                    
                    # Section 1: Pitcher Analysis
                    st.markdown("### ⚾ Starting Pitchers Comparison")
                    
                    col_p1, col_p2 = st.columns(2)
                    
                    for col_p, side, title in [(col_p1, "away", "Away Starting Pitcher"), (col_p2, "home", "Home Starting Pitcher")]:
                        with col_p:
                            p_stats = game_details["pitchers"][side]
                            starter = next((p for p in p_stats if p["is_starter"]), None)
                            if not starter and p_stats:
                                starter = p_stats[0]
                                
                            if starter:
                                st.markdown(f"#### {title}: **{starter['name']}**")
                                
                                # Pitcher basic info
                                st.markdown(f"""
                                - **ERA**: {starter['era']} | **WHIP**: {starter['whip']}
                                - **Strikeouts/9**: {starter['strikeouts_per_9']} | **Walks/9**: {starter['walks_per_9']}
                                - **Innings Pitched**: {starter['innings_pitched']} | **Games Started**: {starter['games_started']}
                                """)
                                
                                # Splits vs Left/Right
                                splits = starter.get("splits", {})
                                split_data = []
                                for hand, label in [("vl", "vs Left-Handed Batters"), ("vr", "vs Right-Handed Batters")]:
                                    s = splits.get(hand, {})
                                    if s:
                                        split_data.append({
                                            "Split": label,
                                            "Opp AVG": s.get("avg", ".000"),
                                            "Opp OBP": s.get("obp", ".000"),
                                            "Opp OPS": s.get("ops", ".000"),
                                            "WHIP": s.get("whip", "0.00")
                                        })
                                if split_data:
                                    st.caption("Splits vs. LHB/RHB:")
                                    st.dataframe(pd.DataFrame(split_data), hide_index=True, use_container_width=True)
                                    
                                # Statcast Expected stats
                                sav = starter.get("savant", {})
                                if sav:
                                    st.markdown(f"""
                                    - **Expected wOBA Allowed (xwOBA)**: `{sav.get('xwoba_against', 'N/A')}`
                                    - **Expected AVG Allowed (xBA)**: `{sav.get('xba_against', 'N/A')}`
                                    - **Barrel% Allowed**: `{sav.get('barrel_rate_against', 'N/A')}%`
                                    """)
                            else:
                                st.warning(f"No starting pitcher stats available for {side} team.")
                                
                    # Plotly chart comparison of Pitcher expected stats
                    if game_analysis["away_pitcher_stats"] and game_analysis["home_pitcher_stats"]:
                        ap = game_analysis["away_pitcher_stats"]
                        hp = game_analysis["home_pitcher_stats"]
                        
                        ap_sav = ap.get("savant", {})
                        hp_sav = hp.get("savant", {})
                        
                        if ap_sav and hp_sav:
                            st.markdown("##### Expected wOBA Against (Lower is Better)")
                            fig = go.Figure(data=[
                                go.Bar(name=ap["name"], x=["xwOBA Against"], y=[analyzer.parse_stat(ap_sav.get("xwoba_against"))], marker_color='#4facfe'),
                                go.Bar(name=hp["name"], x=["xwOBA Against"], y=[analyzer.parse_stat(hp_sav.get("xwoba_against"))], marker_color='#8a2be2')
                            ])
                            fig.update_layout(
                                barmode='group',
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font_color='#0f172a',
                                height=250,
                                margin=dict(l=20, r=20, t=10, b=20)
                            )
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                            
                    # Section 2: Batter Matchups Rating
                    st.markdown("---")
                    st.markdown("### 📈 Hitter Matchup Ratings vs Starters")
                    st.caption("Calculates a matchup rating score (0 to 100) blending heuristic rules (batting order, expected runs, bullpen strength) with a mathematically regressed hit probability model.")
                    
                    col_b1, col_b2 = st.columns(2)
                    
                    for col_b, side, opp_p in [(col_b1, "away_vs_home_pitcher", game_analysis["home_pitcher"]), 
                                               (col_b2, "home_vs_away_pitcher", game_analysis["away_pitcher"])]:
                        with col_b:
                            st.markdown(f"#### Lineup vs **{opp_p}**")
                            matchups = game_analysis["hitter_matchups"][side]
                            
                            if not matchups:
                                st.caption("No matchup ratings calculated for this lineup.")
                            else:
                                df_matchups = []
                                for m in matchups[:8]:
                                    # Form badge representation
                                    score = m["rating"]
                                    if score >= 75.0:
                                        badge = "🟢 Strong"
                                    elif score >= 65.0:
                                        badge = "🟡 Fair"
                                    else:
                                        badge = "🔴 Weak"
                                        
                                    streak_data = mlb_data.get_player_recent_streak(m["player_id"], st.session_state.date_str)
                                    df_matchups.append({
                                        "Batter": m["name"],
                                        "Rating": score,
                                        "Advantage": badge,
                                        "OPS vs Hand": m["ops_vs_hand"],
                                        "Recent Hits": f"{streak_data['hits_in_last_5']}/5 G",
                                        "Streak": f"{streak_data['current_hit_streak']} G",
                                        "xwOBA": m["xwoba"]
                                    })
                                st.dataframe(pd.DataFrame(df_matchups), hide_index=True, use_container_width=True)
                                
                    # Section 3: Matchup Insights
                    st.markdown("---")
                    st.markdown("### 💡 Key Matchup Insights")
                    insights = game_analysis.get("insights", [])
                    
                    if not insights:
                        st.info("No standout mathematical advantages detected for this matchup.")
                    else:
                        for ins in insights:
                            if ins["type"] == "batter_advantage":
                                st.markdown(f"🟢 **Batter Advantage**: {ins['text']}")
                            elif ins["type"] == "pitcher_k_advantage":
                                st.markdown(f"🔵 **Strikeout Target**: {ins['text']}")
                            elif ins["type"] == "pitching_duel":
                                st.markdown(f"🟣 **Game Trend**: {ins['text']}")

# ----------------- TAB 2: DAILY PLAYER TARGETS -----------------
with tab_leaderboards:
    st.markdown("## 🎯 Daily Player Prop Targets")
    st.caption("Ranked lists of players with the highest statistical advantages on today's slate, compiled from platoon splits and Statcast metrics.")
    
    if not full_slate_raw_details:
        st.info("No player stats available for today's slate.")
    else:
        # Run leaderboards analysis
        leaderboards = analyzer.get_daily_leaderboards(full_slate_raw_details)
        
        # Auto-save today's picks behind the scenes
        try:
            analyzer.save_daily_picks(st.session_state.date_str, leaderboards)
        except Exception:
            pass
        
        # 1. PITCHERS STRIKEOUT PROPS
        st.markdown("### 🦹 Pitcher Strikeout Targets")
        col_k_over, col_k_under = st.columns(2)
        
        with col_k_over:
            st.markdown("#### 🔥 Most Likely to Get Strikeouts (OVER Candidates)")
            pk_over = leaderboards["pitchers_k_over"]
            if not pk_over:
                st.caption("No qualified starters today.")
            else:
                df_k_over = []
                for p in pk_over[:5]:
                    df_k_over.append({
                        "Pitcher": p["name"],
                        "Team": p["team"],
                        "Opponent": p["opponent"],
                        "K/9": p["k9"],
                        "K-Score": f"{p['score']}/100",
                        "Matchup Details": p["rationale"].split(". ")[1] if len(p["rationale"].split(". ")) > 1 else p["rationale"]
                    })
                st.dataframe(pd.DataFrame(df_k_over), hide_index=True, use_container_width=True)
                
        with col_k_under:
            st.markdown("#### ❄️ Least Likely to Get Strikeouts (UNDER Candidates)")
            pk_under = leaderboards["pitchers_k_under"]
            if not pk_under:
                st.caption("No qualified starters today.")
            else:
                df_k_under = []
                for p in pk_under[:5]:
                    df_k_under.append({
                        "Pitcher": p["name"],
                        "Team": p["team"],
                        "Opponent": p["opponent"],
                        "K/9": p["k9"],
                        "Under Score": f"{p['under_score']}/100",
                        "Matchup Details": p["rationale"].split(". ")[1] if len(p["rationale"].split(". ")) > 1 else p["rationale"]
                    })
                st.dataframe(pd.DataFrame(df_k_under), hide_index=True, use_container_width=True)
                
        st.markdown("---")
        
        # 2. BATTERS HITS & BASES PROPS
        st.markdown("### ⚾ Batter Hits & Total Bases Targets")
        st.caption("Hitters with the highest matchup ratings on today's slate, blending heuristic rules and regressed probability math.")
        
        b_hits = leaderboards["batters_hits"]
        if not b_hits:
            st.info("No qualified batters today.")
        else:
            df_b_hits = []
            for b in b_hits[:10]:
                streak_data = mlb_data.get_player_recent_streak(b["id"], st.session_state.date_str)
                df_b_hits.append({
                    "Hitter": b["name"],
                    "Team": b["team"],
                    "Matchup": b["game"],
                    "Opponent Pitcher": b["opponent_pitcher"],
                    "Exp Runs": f"{b.get('expected_runs', 4.4):.1f} R",
                    "Hits Score": b["hits_rating"],
                    "Recent Hits": f"{streak_data['hits_in_last_5']}/5 G",
                    "Hit Streak": f"{streak_data['current_hit_streak']} G",
                    "Season AVG": b["avg"],
                    "Season OPS": b["ops"],
                    "Savant xwOBA": b["savant_xwoba"]
                })
            st.dataframe(pd.DataFrame(df_b_hits), hide_index=True, use_container_width=True)
            
        st.markdown("---")
        
        # 3. BATTERS HOME RUN PROPS
        st.markdown("### 🚀 Batter Home Run Targets")
        st.caption("High power-contact hitters (Savant Barrel%) facing starting pitchers vulnerable to giving up home runs (high HR/9 or high Barrel% Allowed). Home Run props carry higher payouts and higher risk.")
        
        b_hr = leaderboards["batters_hr"]
        if not b_hr:
            st.info("No qualified batters today.")
        else:
            df_b_hr = []
            for b in b_hr[:10]:
                streak_data = mlb_data.get_player_recent_streak(b["id"], st.session_state.date_str)
                last_hr = streak_data["last_hr_date"]
                last_hr_disp = last_hr if last_hr and last_hr != "None" else "None this/last season"
                df_b_hr.append({
                    "Hitter": b["name"],
                    "Team": b["team"],
                    "Matchup": b["game"],
                    "Opponent Pitcher": b["opponent_pitcher"],
                    "Exp Runs": f"{b.get('expected_runs', 4.4):.1f} R",
                    "HR Score": f"{b['hr_rating']}/100",
                    "HR Streak": f"{streak_data['current_hr_streak']} G",
                    "Recent Hits": f"{streak_data['hits_in_last_5']}/5 G",
                    "Season HRs": b["home_runs"],
                    "Last HR Date": last_hr_disp,
                    "Savant Barrel%": f"{b['savant_barrel']}%" if isinstance(b['savant_barrel'], float) or b['savant_barrel'] != "TBD" else "TBD",
                    "Savant xwOBA": b["savant_xwoba"]
                })
            st.dataframe(pd.DataFrame(df_b_hr), hide_index=True, use_container_width=True)

# ----------------- TAB 3: PARLAY BUILDER -----------------
with tab_parlays:
    st.markdown("## 📈 Correlated Parlay Suggestions")
    st.caption("These parlays combine highly correlated positive or negative betting conditions (e.g. Pitcher strikeouts OVER matches Opposing Team Total runs UNDER) based on matchup metrics.")
    
    # We can just build them directly using the preloaded full_slate_matchups
    parlays = analyzer.build_parlay_recommendations(full_slate_matchups)
        
    if not parlays:
        st.info("No premium correlated parlays met the qualification score threshold today.")
    else:
        for p in parlays:
            badge_class = "badge-high" if p["confidence"] == "High" else "badge-medium"
            
            # Custom glassmorphic card for parlays
            parlay_html = f"""
            <div style="background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 12px; padding: 2rem; margin-bottom: 1.5rem; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid rgba(15, 23, 42, 0.08); padding-bottom:1rem;">
                    <div>
                        <span class="badge {badge_class}" style="font-size:0.85rem;">{p['confidence']} Confidence</span>
                        <span style="font-size:0.9rem; color:#475569; margin-left:0.8rem;">Match: {p['game']}</span>
                    </div>
                    <div style="font-size:1.1rem; font-weight:600; color:#2563eb;">Score: {p['score']} / 100</div>
                </div>
                <h3 style="color:#0f172a; font-size:1.4rem; margin-top:1.2rem; margin-bottom:1rem;">{p['title']}</h3>
                <div style="background: rgba(241, 245, 249, 0.7); border-radius: 8px; padding: 1.2rem; margin-bottom: 1.2rem;">
            """
            st.markdown(parlay_html, unsafe_allow_html=True)
            
            # Display Legs
            for idx, leg in enumerate(p["legs"]):
                color = "#3b82f6" if leg["direction"] == "OVER" else "#ef4444"
                st.markdown(f"**Leg {idx+1}**: {leg['market']} **<span style='color:{color};'>{leg['direction']}</span>**  \n*{leg['reason']}*", unsafe_allow_html=True)
                
            st.markdown("""
                </div>
                <div style="font-size:0.95rem; color:#334155; line-height:1.5;">
                    <strong>Betting Slip Rationale:</strong><br>
            """ + p["rationale"] + "</div></div>", unsafe_allow_html=True)

# ----------------- TAB 3: AI BETTING ASSISTANT -----------------
with tab_agent:
    st.markdown("## 💬 MLB Bettor Chat Agent")
    st.caption("Ask questions about starting pitcher splits, hitter expected stats, matchup comparisons, and parlay rationales. The agent automatically has access to today's slate stats.")
    
    # Active game context indicator
    if st.session_state.selected_game:
        # Resolve game details for display
        sg_meta = next((g for g in games_slate if g["game_id"] == st.session_state.selected_game), None)
        if sg_meta:
            st.markdown(f"🎯 **Active Context**: Analyzing *{sg_meta['away_team']} @ {sg_meta['home_team']}* game. The AI agent will incorporate these splits in your questions.")
    else:
        st.markdown("🎯 **Active Context**: Analyzing general slate. (Select a game in the first tab to analyze specific players).")
        
    # Quick Action Prompt Buttons
    st.markdown("##### Quick Prompts:")
    q_col1, q_col2, q_col3 = st.columns(3)
    
    quick_prompt = None
    if q_col1.button("🔥 Who are today's best batter matchups?", use_container_width=True):
        quick_prompt = "Who are today's best batter matchups to target for hits or total bases?"
    if q_col2.button("🎯 Show me the top Strikeout OVER candidates", use_container_width=True):
        quick_prompt = "What starting pitchers have the best strikeout matchups today based on K/9 and opponent strikeout rates?"
    if q_col3.button("📈 Suggest a high-scoring correlated parlay", use_container_width=True):
        quick_prompt = "Suggest a correlated parlay for today's slate with detailed Sabermetric reasoning."
        
    # Render Chat History
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    # Input chat text
    user_input = st.chat_input("Ask about today's pitching matchups, hitter splits, or parlay correlations...")
    
    # Override input if quick prompt clicked
    if quick_prompt:
        user_input = quick_prompt
        
    if user_input:
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Generate response
        with st.spinner("AI Agent is analyzing game datasets..."):
            ai_response = agent.generate_chat_response(
                user_input, 
                chat_history=st.session_state.chat_history,
                selected_game_id=st.session_state.selected_game
            )
            
        # Display AI response
        with st.chat_message("assistant"):
            st.markdown(ai_response)
        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
        st.rerun()

# ----------------- TAB 5: RESULTS TRACKER -----------------
with tab_tracker:
    st.markdown("## 📊 Saved Picks & Results Tracker")
    st.caption("Compare your saved selections against actual game boxscores. For pitchers, input the Strikeout Prop Line to dynamically grade wins and losses.")
    
    import glob
    saved_files = glob.glob(os.path.join("saved_picks", "*_picks.json"))
    available_dates = sorted([os.path.basename(f).split("_")[0] for f in saved_files], reverse=True)
    
    if not available_dates:
        st.info("No saved picks found yet. The scheduler will automatically save today's picks at 12:00 PM, or you can trigger it by viewing the 'Player Prop Targets' tab.")
    else:
        import datetime as dt
        try:
            viewed_date = datetime.strptime(st.session_state.date_str, '%Y-%m-%d')
            yesterday_str = (viewed_date - dt.timedelta(days=1)).strftime('%Y-%m-%d')
        except Exception:
            yesterday_str = (datetime.today() - dt.timedelta(days=1)).strftime('%Y-%m-%d')
            
        default_index = 0
        if yesterday_str in available_dates:
            default_index = available_dates.index(yesterday_str)
        elif len(available_dates) > 1:
            default_index = 1
            
        selected_track_date = st.selectbox("Select Date to Track", available_dates, index=default_index)
        
        with st.spinner("Fetching boxscore results and verifying selections..."):
            tracked_data = analyzer.load_and_track_picks(selected_track_date)
            
        if not tracked_data or "results" not in tracked_data:
            st.error("Failed to load results for this date.")
        else:
            results = tracked_data["results"]
            results_completed = tracked_data.get("results_completed", False)
            
            if not results_completed:
                st.warning("⚠️ Some games on this date may still be in progress or scheduled. Final boxscore stats will update fully after 8:00 AM the following morning.")
                
            # 1. Pitchers OVER Table
            st.markdown("### 🦹 Pitcher Strikeout OVER Picks")
            p_over_data = results.get("pitchers_k_over", [])
            if not p_over_data:
                st.caption("No OVER selections saved for this date.")
            else:
                # Read edit dict from session state if it exists
                editor_key = f"editor_over_{selected_track_date}"
                edits = st.session_state.get(editor_key, {}).get("edited_rows", {})
                
                df_p_over = []
                for idx, p in enumerate(p_over_data):
                    state_key = f"line_over_{selected_track_date}_{p['id']}"
                    
                    # Intercept edits in real-time before display
                    if str(idx) in edits and "Line" in edits[str(idx)]:
                        saved_line = edits[str(idx)]["Line"]
                        st.session_state[state_key] = saved_line
                    elif idx in edits and "Line" in edits[idx]:
                        saved_line = edits[idx]["Line"]
                        st.session_state[state_key] = saved_line
                    else:
                        saved_line = st.session_state.get(state_key, 0.0)
                    
                    actual = p["actual_ks"] if p["played"] else 0
                    if not p["played"]:
                        outcome = "⚪ Void"
                    elif saved_line == 0.0:
                        outcome = "📝 Enter Line"
                    else:
                        outcome = "✅ Win" if float(actual) > float(saved_line) else "❌ Loss"
                        
                    df_p_over.append({
                        "Pitcher": p["name"],
                        "Team": p["team"],
                        "Opponent": p["opponent"],
                        "K-Score": f"{p['score']}/100",
                        "Actual Ks": p["actual_ks"] if p["played"] else "Did not pitch",
                        "Innings": p["actual_ip"] if p["played"] else "0.0",
                        "Prop Line": saved_line if saved_line > 0.0 else 0.0,
                        "Outcome": outcome,
                        "PlayerID": p["id"]
                    })
                
                df_p_over_pd = pd.DataFrame(df_p_over)
                edited_over = st.data_editor(
                    df_p_over_pd,
                    column_config={
                        "Prop Line": st.column_config.NumberColumn("Prop Line", min_value=0.0, max_value=20.0, step=0.5, format="%.1f"),
                        "PlayerID": None
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=editor_key
                )
                
                # Save lines to session state on rerun
                for idx, row in edited_over.iterrows():
                    line = row["Prop Line"]
                    pid = row["PlayerID"]
                    st.session_state[f"line_over_{selected_track_date}_{pid}"] = line
                
            st.markdown("---")
            
            # 2. Pitchers UNDER Table
            st.markdown("### ❄️ Pitcher Strikeout UNDER Picks")
            p_under_data = results.get("pitchers_k_under", [])
            if not p_under_data:
                st.caption("No UNDER selections saved for this date.")
            else:
                # Read edit dict from session state if it exists
                editor_key = f"editor_under_{selected_track_date}"
                edits = st.session_state.get(editor_key, {}).get("edited_rows", {})
                
                df_p_under = []
                for idx, p in enumerate(p_under_data):
                    state_key = f"line_under_{selected_track_date}_{p['id']}"
                    
                    # Intercept edits in real-time before display
                    if str(idx) in edits and "Line" in edits[str(idx)]:
                        saved_line = edits[str(idx)]["Line"]
                        st.session_state[state_key] = saved_line
                    elif idx in edits and "Line" in edits[idx]:
                        saved_line = edits[idx]["Line"]
                        st.session_state[state_key] = saved_line
                    else:
                        saved_line = st.session_state.get(state_key, 0.0)
                    
                    actual = p["actual_ks"] if p["played"] else 0
                    if not p["played"]:
                        outcome = "⚪ Void"
                    elif saved_line == 0.0:
                        outcome = "📝 Enter Line"
                    else:
                        outcome = "✅ Win" if float(actual) < float(saved_line) else "❌ Loss"
                        
                    df_p_under.append({
                        "Pitcher": p["name"],
                        "Team": p["team"],
                        "Opponent": p["opponent"],
                        "Under Score": f"{p['under_score']}/100",
                        "Actual Ks": p["actual_ks"] if p["played"] else "Did not pitch",
                        "Innings": p["actual_ip"] if p["played"] else "0.0",
                        "Prop Line": saved_line if saved_line > 0.0 else 0.0,
                        "Outcome": outcome,
                        "PlayerID": p["id"]
                    })
                
                df_p_under_pd = pd.DataFrame(df_p_under)
                edited_under = st.data_editor(
                    df_p_under_pd,
                    column_config={
                        "Prop Line": st.column_config.NumberColumn("Prop Line", min_value=0.0, max_value=20.0, step=0.5, format="%.1f"),
                        "PlayerID": None
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=editor_key
                )
                
                # Save lines to session state on rerun
                for idx, row in edited_under.iterrows():
                    line = row["Prop Line"]
                    pid = row["PlayerID"]
                    st.session_state[f"line_under_{selected_track_date}_{pid}"] = line
                
            st.markdown("---")
            
            # 3. Batters Hits
            st.markdown("### ⚾ Batter Hits Props Outcomes")
            b_hits_data = results.get("batters_hits", [])
            if not b_hits_data:
                st.caption("No hitter hits selections saved for this date.")
            else:
                df_b_hits_res = []
                for b in b_hits_data:
                    if not b["played"]:
                        outcome = "⚪ Void (DNP)"
                    else:
                        outcome = "✅ Win" if b["actual_hits"] >= 1 else "❌ Loss"
                        
                    df_b_hits_res.append({
                        "Hitter": b["name"],
                        "Team": b["team"],
                        "Opponent": b["opponent_team"],
                        "Hits Score": b["score"],
                        "Season AVG": b["avg"],
                        "Actual Hits": b["actual_hits"] if b["played"] else 0,
                        "Outcome": outcome
                    })
                st.dataframe(pd.DataFrame(df_b_hits_res), hide_index=True, use_container_width=True)
                
            st.markdown("---")
            
            # 4. Batters HR
            st.markdown("### 🚀 Batter Home Run Props Outcomes")
            b_hr_data = results.get("batters_hr", [])
            if not b_hr_data:
                st.caption("No home run selections saved for this date.")
            else:
                df_b_hr_res = []
                for b in b_hr_data:
                    if not b["played"]:
                        outcome = "⚪ Void (DNP)"
                    else:
                        outcome = "✅ Win" if b["actual_hrs"] >= 1 else "❌ Loss"
                        
                    df_b_hr_res.append({
                        "Hitter": b["name"],
                        "Team": b["team"],
                        "Opponent": b["opponent_team"],
                        "HR Score": f"{b['score']}/100",
                        "Season HRs": b["home_runs"],
                        "Actual HRs": b["actual_hrs"] if b["played"] else 0,
                        "Outcome": outcome
                    })
                st.dataframe(pd.DataFrame(df_b_hr_res), hide_index=True, use_container_width=True)

# ----------------- TAB 6: UNDER REGRESSION STRATEGY -----------------
with tab_strategy:
    st.markdown("## 📉 Under Regression Betting Strategy")
    
    # Calculate yesterday's date
    import datetime as dt
    yesterday_date_str = (datetime.strptime(st.session_state.date_str, '%Y-%m-%d') - dt.timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Add controls for customizing min hits and min HRs
    col_hits, col_hrs = st.columns(2)
    with col_hits:
        min_hits = st.selectbox(
            "Yesterday's Min Hits Threshold",
            options=[1, 2, 3, 4],
            index=1,  # Default is 2 (index 1 of [1, 2, 3, 4])
            help="Filter for hitters who recorded at least this many hits yesterday."
        )
    with col_hrs:
        min_hrs = st.selectbox(
            "Yesterday's Min HRs Threshold",
            options=[0, 1, 2],
            index=1,  # Default is 1 (index 1 of [0, 1, 2])
            help="Filter for hitters who hit at least this many home runs yesterday."
        )
        
    st.markdown(f"""
    **Regression to the Mean Strategy**: Hits and Total Bases lines are often inflated for players who had outstanding games yesterday due to public visibility. 
    This tab identifies hitters who had **$\\ge {min_hits}$ Hits** or **$\\ge {min_hrs}$ Home Runs** yesterday. If they are playing today and face a tough opposing pitcher (resulting in a **🔴 Weak** or low **Hits Score**), they are high-probability candidates to go **UNDER** on their prop lines today.
    """)
    
    st.markdown(f"### Yesterday's Performance Graded: **{yesterday_date_str}** $\\rightarrow$ Today's Projections: **{st.session_state.date_str}**")
    
    with st.spinner("Compiling regression candidates database..."):
        # We need leaderboards to get Hits Score for today
        if full_slate_raw_details:
            today_leaderboards = analyzer.get_daily_leaderboards(full_slate_raw_details)
            regression_candidates = analyzer.get_under_regression_candidates(
                yesterday_date_str, 
                full_slate_raw_details, 
                today_leaderboards,
                min_hits=min_hits,
                min_hrs=min_hrs
            )
        else:
            regression_candidates = []
            
    if not regression_candidates:
        st.info("No games or candidates found for this date pair.")
    else:
        # Separate into players playing today vs not playing
        playing_today = [c for c in regression_candidates if c["today_game"] != "No Game Today"]
        not_playing = [c for c in regression_candidates if c["today_game"] == "No Game Today"]
        
        st.markdown(f"#### 🎯 Active Regression Candidates Today ({len(playing_today)} players)")
        st.caption("Hitters sorted with the *lowest* Hits Score first (best candidates for an UNDER bet).")
        
        if not playing_today:
            st.info("None of yesterday's hot hitters are scheduled to play today.")
        else:
            df_playing = []
            for c in playing_today:
                df_playing.append({
                    "Hitter": c["name"],
                    "Team": c["team"],
                    "Yesterday's Performance": c["yesterday_stat"],
                    "Today's Matchup": c["today_game"],
                    "Opposing Pitcher": c["opponent_pitcher"],
                    "Season Hits/Game": c["hits_per_game"],
                    "Season Hits/PA": c["hits_per_pa"],
                    "Today's Hits Score": c["hits_score"],
                    "Matchup Rating": c["advantage"]
                })
            
            # Format and display
            st.dataframe(
                pd.DataFrame(df_playing),
                column_config={
                    "Season Hits/Game": st.column_config.NumberColumn("Season Hits/Game", format="%.2f"),
                    "Season Hits/PA": st.column_config.NumberColumn("Season Hits/PA", format="%.3f"),
                    "Today's Hits Score": st.column_config.NumberColumn("Today's Hits Score", format="%.1f")
                },
                hide_index=True,
                use_container_width=True
            )
            
        if not_playing:
            with st.expander(f"😴 Players Not Playing Today ({len(not_playing)} players)", expanded=False):
                df_not_playing = []
                for c in not_playing:
                    df_not_playing.append({
                        "Hitter": c["name"],
                        "Team": c["team"],
                        "Yesterday's Performance": c["yesterday_stat"]
                    })
                st.dataframe(pd.DataFrame(df_not_playing), hide_index=True, use_container_width=True)
