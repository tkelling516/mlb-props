import os
import json
from datetime import datetime, timedelta

def parse_stat(value, default=0.0):
    """Utility to safely parse stats as floats."""
    if value is None or value == ".---" or value == "-.--":
        return default
    try:
        if isinstance(value, str) and value.startswith('.'):
            return float("0" + value)
        return float(value)
    except ValueError:
        return default

def parse_innings(ip_val):
    """Safely parse baseball innings pitched (e.g. '50.1' -> 50.33, '5.0' -> 5.0) as float."""
    if ip_val is None:
        return 0.0
    try:
        ip_str = str(ip_val).strip()
        if not ip_str or ip_str == "0.0":
            return 0.0
        parts = ip_str.split('.')
        innings = float(parts[0])
        if len(parts) > 1:
            outs = float(parts[1])
            innings += outs / 3.0
        return innings
    except Exception:
        return 0.0

def get_bullpen_stats(pitchers_list):
    """
    Calculate bullpen strength: average ERA and WHIP of non-starting pitchers in the list.
    """
    relievers = [p for p in pitchers_list if not p.get("is_starter")]
    eras = []
    whips = []
    for r in relievers:
        era = parse_stat(r.get("era"))
        whip = parse_stat(r.get("whip"))
        if era > 0.0:
            eras.append(era)
        if whip > 0.0:
            whips.append(whip)
            
    avg_era = sum(eras) / len(eras) if eras else 4.20
    avg_whip = sum(whips) / len(whips) if whips else 1.30
    return {"era": avg_era, "whip": avg_whip}

def estimate_expected_runs(team_side, game_data):
    """
    Estimate expected runs for a team (away or home) in a game.
    Considers starting lineup season OPS, opposing starting pitcher stats,
    opposing bullpen strength, and venue park factor.
    """
    # 1. Lineup OPS
    starters = [b for b in game_data["players"][team_side] if b.get("is_starter")]
    if not starters:
        starters = game_data["players"][team_side]
        
    ops_list = [parse_stat(b.get("ops")) for b in starters if parse_stat(b.get("ops")) > 0]
    avg_ops = sum(ops_list) / len(ops_list) if ops_list else 0.720
    
    # 2. Opposing Pitchers
    opp_side = "home" if team_side == "away" else "away"
    opp_pitchers = game_data["pitchers"][opp_side]
    
    opp_starter = next((p for p in opp_pitchers if p.get("is_starter")), None)
    if not opp_starter and opp_pitchers:
        opp_starter = opp_pitchers[0]
        
    if opp_starter:
        starter_era = parse_stat(opp_starter.get("era"))
        if starter_era == 0.0 or opp_starter.get("era") == "-.--":
            starter_era = 4.20
    else:
        starter_era = 4.20
        
    # Bullpen strength
    bp_stats = get_bullpen_stats(opp_pitchers)
    bullpen_era = bp_stats["era"]
    
    # Blend starter and bullpen based on starter games started and IP
    starter_gs = parse_stat(opp_starter.get("games_started")) if opp_starter else 0
    starter_ip = parse_innings(opp_starter.get("innings_pitched")) if opp_starter else 0
    ip_per_start = starter_ip / starter_gs if starter_gs > 0 else 5.0
    
    ip_per_start = max(2.0, min(7.0, ip_per_start))
    starter_weight = ip_per_start
    bullpen_weight = 9.0 - starter_weight
    
    effective_era = (starter_era * starter_weight + bullpen_era * bullpen_weight) / 9.0
    
    # 3. Park Factor Multiplier
    venue = str(game_data.get("venue_name", "")).lower()
    park_multiplier = 1.0
    high_parks = ["coors", "great american", "citizens bank", "guaranteed rate", "american family", "fenway", "wrigley"]
    low_parks = ["oracle", "t-mobile", "loandepot", "comerica", "petco", "oakland coliseum", "tropicana"]
    
    for p in high_parks:
        if p in venue:
            park_multiplier = 1.15
            break
    for p in low_parks:
        if p in venue:
            park_multiplier = 0.85
            break
            
    ops_factor = avg_ops / 0.720
    pitching_factor = effective_era / 4.20
    
    # Bound factors
    ops_factor = max(0.75, min(1.35, ops_factor))
    pitching_factor = max(0.65, min(1.45, pitching_factor))
    
    expected_runs = 4.40 * ops_factor * pitching_factor * park_multiplier
    return round(expected_runs, 2)

def calculate_matchup_rating(hitter, pitcher, pitcher_hand="R", expected_team_runs=4.4, bullpen_era=4.20, streak_data=None, is_home=False):
    """
    Calculate a matchup rating score (0-100) representing a blend of heuristic rules
    and a mathematically regressed hit probability model.
    """
    # 1. Estimate Expected Plate Appearances (PA_est) based on Batting Order Position
    batting_order = hitter.get("batting_order", -1)
    
    # Calculate seasonal Plate Appearances per Game (PA/G) as a fallback
    h_pa = parse_stat(hitter.get("plate_appearances"))
    h_games = parse_stat(hitter.get("games_played"))
    pa_per_game = h_pa / h_games if h_games > 0 else 0.0
    
    if batting_order == -1 and pa_per_game > 0.0:
        # Fallback: Use seasonal PA per game
        base_pa = max(3.50, min(4.70, pa_per_game))
        # Map back to estimated batting order for heuristic scoring bonuses
        if pa_per_game >= 4.40:
            batting_order = 2  # treated as 1-2 (leadoff/2-hole)
        elif pa_per_game >= 4.15:
            batting_order = 4  # treated as 3-4
        elif pa_per_game < 3.70:
            batting_order = 8  # treated as 8-9
        else:
            batting_order = 6  # treated as 5-7 (neutral)
    else:
        pa_map = {
            1: 4.65,
            2: 4.50,
            3: 4.35,
            4: 4.20,
            5: 4.05,
            6: 3.90,
            7: 3.80,
            8: 3.70,
            9: 3.60
        }
        base_pa = pa_map.get(batting_order, 3.50)
    
    # Adjust for expected team runs (more runs -> more times through the order)
    runs_adjustment = (expected_team_runs - 4.4) * 0.12
    
    # Adjust for Home vs. Away team (Away team batters guaranteed to bat 9th inning)
    home_away_adjustment = -0.12 if is_home else 0.12
    
    pa_est = base_pa + runs_adjustment + home_away_adjustment
    pa_est = max(2.5, min(5.5, pa_est))
    
    # 2. Estimate Expected At-Bats (AB_est) by removing walks
    h_pa = parse_stat(hitter.get("plate_appearances"))
    h_bb = parse_stat(hitter.get("walks"))
    h_bb_rate = h_bb / max(1.0, h_pa) if h_pa > 0 else 0.08
    
    # Pitcher wildness adjustment to walk rate
    p_bb9 = parse_stat(pitcher.get("walks_per_9"))
    p_bb9_factor = p_bb9 / 3.2 if p_bb9 > 0 else 1.0
    bb_rate_adj = h_bb_rate * p_bb9_factor
    bb_rate_adj = max(0.02, min(0.25, bb_rate_adj))
    
    # At-bats estimate (allowing 1% for HBP and sacrifices)
    ab_est = pa_est * (1.0 - bb_rate_adj - 0.01)
    
    # 3. Regress Hitter Baseline splits and season average
    hitter_hand_code = "vl" if pitcher_hand == "L" else "vr"
    hitter_splits = hitter.get("splits", {}).get(hitter_hand_code, {})
    
    hitter_avg_split = parse_stat(hitter_splits.get("avg"))
    hitter_avg = parse_stat(hitter.get("avg"))
    
    # Empirical Bayes Shrinkage for Hitter AVG
    h_pa_reg = max(0.0, h_pa)
    h_season_weight = h_pa_reg / (h_pa_reg + 60.0) if h_pa_reg > 0 else 0.0
    h_avg_season_regressed = h_season_weight * hitter_avg + (1.0 - h_season_weight) * 0.245
    
    # Regress split AVG toward regressed season AVG
    split_pa = parse_stat(hitter_splits.get("plateAppearances"))
    h_split_weight = split_pa / (split_pa + 40.0) if split_pa > 0 else 0.0
    h_avg_baseline = h_split_weight * hitter_avg_split + (1.0 - h_split_weight) * h_avg_season_regressed
    
    # Blend with Savant expected batting average (xBA)
    h_savant = hitter.get("savant", {})
    xba = parse_stat(h_savant.get("xba"))
    if xba > 0.0:
        xba_regressed = h_season_weight * xba + (1.0 - h_season_weight) * 0.245
        h_avg_baseline = 0.6 * h_avg_baseline + 0.4 * xba_regressed
        
    # 4. Regress Pitcher splits and stats allowed
    bat_side = hitter.get("splits", {}).get("bat_side", "R")
    if bat_side == "S":
        pitcher_split_code = "vr" if pitcher_hand == "L" else "vl"
    else:
        pitcher_split_code = "vl" if bat_side == "L" else "vr"
        
    pitcher_splits = pitcher.get("splits", {}).get(pitcher_split_code, {})
    p_avg_split = parse_stat(pitcher_splits.get("avg"))
    
    p_era = parse_stat(pitcher.get("era"), 4.20)
    p_whip = parse_stat(pitcher.get("whip"), 1.30)
    p_avg_allowed = parse_stat(pitcher.get("avg_allowed"), 0.250)
    
    starter_gs = parse_stat(pitcher.get("games_started"))
    ip_val = parse_innings(pitcher.get("innings_pitched"))
    
    # Regress pitcher season stats
    p_season_weight = ip_val / (ip_val + 25.0) if ip_val > 0 else 0.0
    p_era_regressed = p_season_weight * p_era + (1.0 - p_season_weight) * 4.20
    p_whip_regressed = p_season_weight * p_whip + (1.0 - p_season_weight) * 1.30
    p_avg_allowed_regressed = p_season_weight * p_avg_allowed + (1.0 - p_season_weight) * 0.250
    
    p_season_avg_allowed = max(0.200, min(0.320, p_avg_allowed_regressed))
    
    # Regress pitcher split average allowed
    p_bf_split = parse_stat(pitcher_splits.get("battersFaced"))
    p_split_weight = p_bf_split / (p_bf_split + 50.0) if p_bf_split > 0 else 0.0
    p_avg_baseline = p_split_weight * p_avg_split + (1.0 - p_split_weight) * p_season_avg_allowed
    
    # Blend with Savant expected AVG allowed (xBA against)
    p_savant = pitcher.get("savant", {})
    p_xba_ag = parse_stat(p_savant.get("xba_against"))
    if p_xba_ag > 0.0:
        p_xba_ag_regressed = p_season_weight * p_xba_ag + (1.0 - p_season_weight) * 0.250
        p_avg_baseline = 0.6 * p_avg_baseline + 0.4 * p_xba_ag_regressed
        
    # Pitcher factor
    pitcher_factor = p_avg_baseline / 0.245
    pitcher_factor = max(0.80, min(1.25, pitcher_factor))
    
    # Blended Matchup AVG vs Starter
    avg_vs_starter = h_avg_baseline * pitcher_factor
    
    # Blended Matchup AVG vs Bullpen
    bullpen_factor = bullpen_era / 4.20
    bullpen_factor = max(0.85, min(1.15, bullpen_factor))
    avg_vs_bullpen = h_avg_baseline * bullpen_factor
    
    # Blend starter/bullpen based on starter longevity
    ip_per_start = ip_val / starter_gs if starter_gs > 0 else 5.0
    ip_per_start = max(2.0, min(7.5, ip_per_start))
    
    starter_weight = ip_per_start / 9.0
    bullpen_weight = 1.0 - starter_weight
    
    avg_blended = (avg_vs_starter * starter_weight) + (avg_vs_bullpen * bullpen_weight)
    
    # 5. Strikeout Matchup Adjustment
    h_so = parse_stat(hitter.get("strikeouts"))
    h_so_rate = h_so / max(1.0, h_pa) if h_pa > 0 else 0.20
    p_k9 = parse_stat(pitcher.get("strikeouts_per_9"))
    
    if h_so_rate > 0.25 and p_k9 > 9.0:
        avg_blended -= 0.015
    elif h_so_rate < 0.15 and p_k9 < 8.0:
        avg_blended += 0.015
        
    # 6. Streak Adjustments
    streak_adj = 0.0
    if streak_data:
        hits_in_last_5 = streak_data.get("hits_in_last_5", 0)
        current_hit_streak = streak_data.get("current_hit_streak", 0)
        if hits_in_last_5 >= 4:
            streak_adj += 0.010
        elif hits_in_last_5 <= 1:
            streak_adj -= 0.015
        if current_hit_streak >= 3:
            streak_adj += 0.005 * min(5, current_hit_streak)
            
    streak_adj = max(-0.025, min(0.025, streak_adj))
    avg_blended += streak_adj
    
    # Calculate pure hit probability: 1 - (1 - avg_blended)^ab_est
    hit_prob = 1.0 - ((1.0 - avg_blended) ** ab_est)
    hit_prob_pct = hit_prob * 100.0
    
    # 7. Heuristic Score (Improved Version)
    heur_score = 50.0
    h_ops = parse_stat(hitter_splits.get("ops"))
    if h_ops == 0.0:
        h_ops = parse_stat(hitter.get("ops"))
    
    if h_ops > 0.900:
        heur_score += 15
    elif h_ops > 0.800:
        heur_score += 10
    elif h_ops > 0.700:
        heur_score += 5
    elif h_ops < 0.600:
        heur_score -= 10
    elif h_ops < 0.500:
        heur_score -= 15

    p_splits_l = pitcher.get("splits", {}).get("vl", {})
    p_splits_r = pitcher.get("splits", {}).get("vr", {})
    p_ops_l = parse_stat(p_splits_l.get("ops"))
    p_ops_r = parse_stat(p_splits_r.get("ops"))
    max_p_ops = max(p_ops_l, p_ops_r)
    if max_p_ops > 0.850:
        heur_score += 8
    elif max_p_ops > 0.780:
        heur_score += 5
    elif max_p_ops < 0.650 and max_p_ops > 0:
        heur_score -= 8

    # Hitter Savant (xwoba and barrel)
    h_xwoba = parse_stat(h_savant.get("xwoba"))
    h_barrel = parse_stat(h_savant.get("barrel_rate"))
    if h_xwoba > 0.360:
        heur_score += 10
    elif h_xwoba > 0.330:
        heur_score += 5
    elif h_xwoba < 0.280 and h_xwoba > 0:
        heur_score -= 5
    if h_barrel > 12.0:
        heur_score += 7
    elif h_barrel > 8.0:
        heur_score += 3

    # Pitcher Savant
    p_xwoba_ag = parse_stat(p_savant.get("xwoba_against"))
    p_barrel_ag = parse_stat(p_savant.get("barrel_rate_against"))
    if p_xwoba_ag > 0.340:
        heur_score += 8
    elif p_xwoba_ag > 0.315:
        heur_score += 4
    elif p_xwoba_ag < 0.270 and p_xwoba_ag > 0:
        heur_score -= 8
    if p_barrel_ag > 9.0:
        heur_score += 5
    elif p_barrel_ag < 5.0 and p_barrel_ag > 0:
        heur_score -= 5

    # Strikeout Matchup
    h_so_pct = parse_stat(hitter.get("strikeouts")) / max(1, parse_stat(hitter.get("plate_appearances")))
    p_k_9 = parse_stat(pitcher.get("strikeouts_per_9"))
    if h_so_pct > 0.26 and p_k_9 > 9.5:
        heur_score -= 6

    # Batting order
    if 1 <= batting_order <= 2:
        heur_score += 8.0
    elif 3 <= batting_order <= 4:
        heur_score += 4.0
    elif batting_order >= 8:
        heur_score -= 6.0

    # Contact rate / low K
    if h_pa > 40:
        if h_so_pct < 0.15:
            heur_score += 6.0
        elif h_so_pct > 0.28:
            heur_score -= 6.0

    # Walk risk
    h_bb = parse_stat(hitter.get("walks"))
    bb_rate = h_bb / max(1.0, h_pa)
    p_bb9 = parse_stat(pitcher.get("walks_per_9"))
    if h_pa > 40 and bb_rate > 0.12 and p_bb9 > 3.8:
        heur_score -= 4.0

    # Streak
    if streak_data:
        hits_in_last_5 = streak_data.get("hits_in_last_5", 0)
        current_hit_streak = streak_data.get("current_hit_streak", 0)
        if hits_in_last_5 >= 4:
            heur_score += 5.0
        elif hits_in_last_5 <= 1:
            heur_score -= 6.0
        if current_hit_streak >= 3:
            heur_score += min(7.0, current_hit_streak * 1.0)

    # Runs environment
    if expected_team_runs >= 4.8:
        runs_diff = expected_team_runs - 4.4
        heur_score += min(6.0, runs_diff * 1.5)
    elif expected_team_runs <= 4.0:
        runs_diff = 4.4 - expected_team_runs
        heur_score -= min(6.0, runs_diff * 1.5)

    # Bullpen
    if bullpen_era >= 4.60:
        heur_score += 3.0
    elif bullpen_era <= 3.40:
        heur_score -= 3.0

    # Final Blended Score: 50% Heuristic, 50% Regressed Probability
    final_score = 0.5 * heur_score + 0.5 * hit_prob_pct
    return round(max(0.0, min(100.0, final_score)), 1)

def analyze_pitcher_strikeouts(pitcher, opponent_batters):
    """
    Analyze pitcher strikeout potential vs. opposing lineup.
    Returns a score (0-100) indicating K OVER probability.
    """
    if not pitcher or pitcher.get("era") == "-.--":
        return 0.0, "Insufficient stats"
        
    # Pitcher K ability (K/9)
    p_k9 = parse_stat(pitcher.get("strikeouts_per_9"))
    p_k_score = 0.0
    
    if p_k9 > 11.0:
        p_k_score = 45
    elif p_k9 > 10.0:
        p_k_score = 38
    elif p_k9 > 9.0:
        p_k_score = 30
    elif p_k9 > 8.0:
        p_k_score = 22
    else:
        p_k_score = 12
        
    # Opponent Lineup Strikeout Vulnerability vs. Pitcher Hand
    pitcher_hand = pitcher.get("splits", {}).get("pitch_hand", "R")
    hitter_split_code = "vl" if pitcher_hand == "L" else "vr"
    
    opp_k_rates = []
    active_batters = [b for b in opponent_batters if b.get("is_starter")]
    if not active_batters:
        active_batters = opponent_batters
        
    for batter in active_batters:
        splits = batter.get("splits", {}).get(hitter_split_code, {})
        split_so = parse_stat(splits.get("strikeOuts"))
        split_pa = parse_stat(splits.get("plateAppearances"))
        
        if split_pa > 10:
            opp_k_rates.append(split_so / split_pa)
        else:
            # Fallback to season stats
            so = parse_stat(batter.get("strikeouts"))
            pa = parse_stat(batter.get("plate_appearances"))
            if pa > 20:
                opp_k_rates.append(so / pa)
            
    if opp_k_rates:
        avg_team_k_rate = sum(opp_k_rates) / len(opp_k_rates)
    else:
        avg_team_k_rate = 0.20  # League average default
        
    team_k_score = 0.0
    if avg_team_k_rate > 0.26:
        team_k_score = 45
    elif avg_team_k_rate > 0.23:
        team_k_score = 35
    elif avg_team_k_rate > 0.20:
        team_k_score = 25
    elif avg_team_k_rate > 0.17:
        team_k_score = 15
    else:
        team_k_score = 5
        
    # Pitcher Whiff% / Dominance proxy (WHIP)
    whiff_score = 0.0
    p_whip = parse_stat(pitcher.get("whip"))
    if p_whip < 1.10 and p_whip > 0:
        whiff_score = 10
    elif p_whip < 1.25 and p_whip > 0:
        whiff_score = 5
        
    total_k_score = p_k_score + team_k_score + whiff_score

    # Outing Longevity Factor (IP per start)
    games_started = parse_stat(pitcher.get("games_started"))
    if games_started > 0:
        ip_per_start = parse_innings(pitcher.get("innings_pitched")) / games_started
    else:
        games_played = parse_stat(pitcher.get("games_played"))
        if games_played > 0:
            ip_per_start = parse_innings(pitcher.get("innings_pitched")) / games_played
        else:
            ip_per_start = 0.0

    if ip_per_start >= 5.5:
        total_k_score += 6.0
    elif ip_per_start >= 5.0:
        total_k_score += 3.0
    elif 0 < ip_per_start < 4.2:
        total_k_score -= 6.0

    # Pitcher BB/9 wildness penalty
    p_bb9 = parse_stat(pitcher.get("walks_per_9"))
    if p_bb9 > 3.8:
        total_k_score -= 5.0
    elif 0 < p_bb9 < 2.2:
        total_k_score += 3.0

    # Hand split K rate adjustments
    if avg_team_k_rate > 0.25:
        total_k_score += 10.0
    elif avg_team_k_rate < 0.18:
        total_k_score -= 8.0
        
    # Generate rationale
    arm_type = "LHP" if pitcher_hand == "L" else "RHP"
    rationale = f"Pitcher is {arm_type} with K/9: {p_k9} (walks/9: {p_bb9}, IP/start: {ip_per_start:.1f}). "
    rationale += f"Opponent vs. {arm_type} split K rate is {avg_team_k_rate*100:.1f}%."
    
    return round(max(0.0, min(100.0, total_k_score)), 1), rationale

def get_game_matchups(game_data):
    """Analyze all batter-pitcher matchups for a game and find key insights."""
    if not game_data:
        return None
        
    import mlb_data
    date_str = game_data.get("date", datetime.today().strftime('%Y-%m-%d'))
        
    # Find starting pitchers
    away_starter = next((p for p in game_data["pitchers"]["away"] if p["is_starter"]), None)
    home_starter = next((p for p in game_data["pitchers"]["home"] if p["is_starter"]), None)
    
    # If no starter marked, default to the first pitcher in list
    if not away_starter and game_data["pitchers"]["away"]:
        away_starter = game_data["pitchers"]["away"][0]
    if not home_starter and game_data["pitchers"]["home"]:
        home_starter = game_data["pitchers"]["home"][0]
        
    # Precompute team expected runs and bullpen stats
    away_expected_runs = estimate_expected_runs("away", game_data)
    home_expected_runs = estimate_expected_runs("home", game_data)
    
    away_bp = get_bullpen_stats(game_data["pitchers"]["away"])
    home_bp = get_bullpen_stats(game_data["pitchers"]["home"])
        
    analysis = {
        "game_id": game_data["game_id"],
        "away_team": game_data["away_team"],
        "home_team": game_data["home_team"],
        "away_pitcher": away_starter["name"] if away_starter else "TBD",
        "home_pitcher": home_starter["name"] if home_starter else "TBD",
        "away_pitcher_stats": away_starter,
        "home_pitcher_stats": home_starter,
        "hitter_matchups": {"away_vs_home_pitcher": [], "home_vs_away_pitcher": []},
        "pitcher_strikeouts": {"away_pitcher": {}, "home_pitcher": {}},
        "insights": [],
        "away_expected_runs": away_expected_runs,
        "home_expected_runs": home_expected_runs
    }
    
    # 1. Analyze Away Batters vs. Home Starter
    if home_starter:
        p_hand = home_starter.get("splits", {}).get("pitch_hand", "R")
        for hitter in game_data["players"]["away"]:
            if (hitter["is_starter"] or hitter.get("plate_appearances", 0) > 50) and hitter.get("plate_appearances", 0) >= 80:
                try:
                    streak = mlb_data.get_player_recent_streak(hitter["id"], date_str)
                except Exception:
                    streak = None
                rating = calculate_matchup_rating(
                    hitter, home_starter, p_hand,
                    expected_team_runs=away_expected_runs,
                    bullpen_era=home_bp["era"],
                    streak_data=streak,
                    is_home=False
                )
                analysis["hitter_matchups"]["away_vs_home_pitcher"].append({
                    "player_id": hitter["id"],
                    "name": hitter["name"],
                    "position": hitter["position"],
                    "rating": rating,
                    "avg_vs_hand": hitter.get("splits", {}).get("vr" if p_hand == "R" else "vl", {}).get("avg", hitter["avg"]),
                    "ops_vs_hand": hitter.get("splits", {}).get("vr" if p_hand == "R" else "vl", {}).get("ops", hitter["ops"]),
                    "xwoba": hitter.get("savant", {}).get("xwoba", 0.0),
                    "barrel_rate": hitter.get("savant", {}).get("barrel_rate", 0.0)
                })
                
    # 2. Analyze Home Batters vs. Away Starter
    if away_starter:
        p_hand = away_starter.get("splits", {}).get("pitch_hand", "R")
        for hitter in game_data["players"]["home"]:
            if (hitter["is_starter"] or hitter.get("plate_appearances", 0) > 50) and hitter.get("plate_appearances", 0) >= 80:
                try:
                    streak = mlb_data.get_player_recent_streak(hitter["id"], date_str)
                except Exception:
                    streak = None
                rating = calculate_matchup_rating(
                    hitter, away_starter, p_hand,
                    expected_team_runs=home_expected_runs,
                    bullpen_era=away_bp["era"],
                    streak_data=streak,
                    is_home=True
                )
                analysis["hitter_matchups"]["home_vs_away_pitcher"].append({
                    "player_id": hitter["id"],
                    "name": hitter["name"],
                    "position": hitter["position"],
                    "rating": rating,
                    "avg_vs_hand": hitter.get("splits", {}).get("vr" if p_hand == "R" else "vl", {}).get("avg", hitter["avg"]),
                    "ops_vs_hand": hitter.get("splits", {}).get("vr" if p_hand == "R" else "vl", {}).get("ops", hitter["ops"]),
                    "xwoba": hitter.get("savant", {}).get("xwoba", 0.0),
                    "barrel_rate": hitter.get("savant", {}).get("barrel_rate", 0.0)
                })
                
    # Sort hitter matchups by rating descending
    analysis["hitter_matchups"]["away_vs_home_pitcher"].sort(key=lambda x: x["rating"], reverse=True)
    analysis["hitter_matchups"]["home_vs_away_pitcher"].sort(key=lambda x: x["rating"], reverse=True)
    
    # 3. Analyze Pitcher Ks
    if away_starter:
        k_score, k_rat = analyze_pitcher_strikeouts(away_starter, game_data["players"]["home"])
        analysis["pitcher_strikeouts"]["away_pitcher"] = {
            "name": away_starter["name"],
            "score": k_score,
            "rationale": k_rat,
            "k9": away_starter.get("strikeouts_per_9")
        }
    if home_starter:
        k_score, k_rat = analyze_pitcher_strikeouts(home_starter, game_data["players"]["away"])
        analysis["pitcher_strikeouts"]["home_pitcher"] = {
            "name": home_starter["name"],
            "score": k_score,
            "rationale": k_rat,
            "k9": home_starter.get("strikeouts_per_9")
        }
        
    # Generate insights list
    if away_starter and home_starter:
        p_away_whip = parse_stat(away_starter.get("whip"))
        p_home_whip = parse_stat(home_starter.get("whip"))
        p_away_era = parse_stat(away_starter.get("era"))
        p_home_era = parse_stat(home_starter.get("era"))
        
        if p_away_whip < 1.15 and p_home_whip < 1.15 and p_away_whip > 0 and p_home_whip > 0:
            analysis["insights"].append({
                "type": "pitching_duel",
                "text": f"Elite pitching matchup: {away_starter['name']} (ERA {p_away_era}) vs {home_starter['name']} (ERA {p_home_era}). High potential for Game UNDER runs."
            })
            
        # Top hitters to target
        for side, opp_pitcher_name in [("away_vs_home_pitcher", home_starter["name"]), ("home_vs_away_pitcher", away_starter["name"])]:
            matchups = analysis["hitter_matchups"][side]
            if matchups:
                top_h = matchups[0]
                if top_h["rating"] > 75:
                    analysis["insights"].append({
                        "type": "batter_advantage",
                        "text": f"Advantage Hitter: {top_h['name']} has an excellent matchup vs {opp_pitcher_name} (Matchup Rating: {top_h['rating']}). Target Hits/Bases OVER."
                    })
                    
        # Pitcher K targets
        for side in ["away_pitcher", "home_pitcher"]:
            k_data = analysis["pitcher_strikeouts"][side]
            if k_data and k_data.get("score", 0) > 75:
                analysis["insights"].append({
                    "type": "pitcher_k_advantage",
                    "text": f"High Strikeout Target: {k_data['name']} has a favorable matchup for Strikeouts OVER (K Score: {k_data['score']}). {k_data['rationale']}"
                })
                
    return analysis

def build_parlay_recommendations(all_games_analysis):
    """
    Analyze matchups across all games on the slate to suggest correlated parlays.
    """
    parlays = []
    
    for game in all_games_analysis:
        if not game:
            continue
            
        game_id = game["game_id"]
        away_team = game["away_team"]
        home_team = game["home_team"]
        
        away_starter_name = game["away_pitcher"]
        home_starter_name = game["home_pitcher"]
        
        # 1. Pitcher Strikeout OVER + Opposing Team Runs UNDER (Correlated Parlay 1)
        for side, opp_side, pitcher_name, opp_team in [("away_pitcher", "home_pitcher", away_starter_name, home_team), 
                                                        ("home_pitcher", "away_pitcher", home_starter_name, away_team)]:
            k_data = game["pitcher_strikeouts"].get(side, {})
            if k_data and k_data.get("score", 0) > 65:
                score = k_data["score"]
                conf = "High" if score > 78 else "Medium"
                
                parlays.append({
                    "game_id": game_id,
                    "game": f"{away_team} @ {home_team}",
                    "title": f"Correlated Pitcher & Under Parlay ({pitcher_name})",
                    "confidence": conf,
                    "score": score,
                    "legs": [
                        {"market": f"{pitcher_name} Strikeouts", "direction": "OVER", "reason": f"Pitcher strikeout strength score is {score}. {k_data.get('rationale')}"},
                        {"market": f"{opp_team} Total Runs", "direction": "UNDER", "reason": f"Correlated: High strikeouts prevent offensive scoring and base runners."}
                    ],
                    "rationale": f"High K rate pitchers naturally suppress team run scoring. {pitcher_name} is in a prime position to record high strikeouts, which directly correlates with keeping the {opp_team} total runs low."
                })
                
        # 2. Hot Hitter OVER + Hitter's Team Runs OVER (Correlated Parlay 2)
        for side, team, opp_pitcher_name in [("away_vs_home_pitcher", away_team, home_starter_name), 
                                             ("home_vs_away_pitcher", home_team, away_starter_name)]:
            matchups = game["hitter_matchups"].get(side, [])
            if matchups:
                top_hitter = matchups[0]
                if top_hitter["rating"] > 72:
                    score = top_hitter["rating"]
                    conf = "High" if score > 80 else "Medium"
                    
                    parlays.append({
                        "game_id": game_id,
                        "game": f"{away_team} @ {home_team}",
                        "title": f"Correlated Offense Parlay ({top_hitter['name']})",
                        "confidence": conf,
                        "score": score,
                        "legs": [
                            {"market": f"{top_hitter['name']} Hits / Total Bases", "direction": "OVER", "reason": f"Matchup Rating is {score} vs {opp_pitcher_name}. Splits OPS: {top_hitter['ops_vs_hand']}, xwOBA: {top_hitter['xwoba']}"},
                            {"market": f"{team} Team Total Runs", "direction": "OVER", "reason": f"Correlated: If key hitters have outstanding matchups, the team is highly likely to score runs."}
                        ],
                        "rationale": f"If {top_hitter['name']} has a productive day (Hits/Total Bases OVER), it directly contributes to run production for the {team}. This creates a highly correlated positive offensive game state."
                    })
                    
        # 3. Game Under + Starting Pitchers Under Runs (Correlated Parlay 3)
        duel_insights = [i for i in game.get("insights", []) if i["type"] == "pitching_duel"]
        if duel_insights:
            parlays.append({
                "game_id": game_id,
                "game": f"{away_team} @ {home_team}",
                "title": "Elite Pitching Duel Game UNDER Parlay",
                "confidence": "High",
                "score": 85.0,
                "legs": [
                    {"market": f"Game Total Runs ({away_team} @ {home_team})", "direction": "UNDER", "reason": "Dual ace matchup suppresses scoring on both sides."},
                    {"market": f"{away_starter_name} Earned Runs Allowed", "direction": "UNDER", "reason": f"Ace pitcher starting (WHIP: {game['away_pitcher_stats'].get('whip')})"},
                    {"market": f"{home_starter_name} Earned Runs Allowed", "direction": "UNDER", "reason": f"Ace pitcher starting (WHIP: {game['home_pitcher_stats'].get('whip')})"}
                ],
                "rationale": "When two premium pitchers face off, game totals are suppressed. This parlay captures both starting pitchers staying under their runs allowed, which mathematically locks in the game total staying UNDER."
            })
            
    parlays.sort(key=lambda x: x["score"], reverse=True)
    return parlays

def calculate_hr_rating(hitter, pitcher, pitcher_hand="R", venue_name="TBD", expected_team_runs=4.4, bullpen_era=4.20, streak_data=None):
    """
    Calculate a Home Run Rating score (0-100) for a hitter facing a starting pitcher.
    Higher score indicates a higher probability of hitting a home run.
    """
    score = 10.0
    
    # 1. Hitter season power stats
    h_hr = parse_stat(hitter.get("home_runs"))
    h_pa = parse_stat(hitter.get("plate_appearances"))
    hr_rate = h_hr / max(1.0, h_pa)  # average ~3.0%
    
    power_points = min(30.0, hr_rate * 500.0) 
    score += power_points
    
    # 2. Hitter Statcast Barrel Rate (max 25 points)
    h_savant = hitter.get("savant", {})
    h_barrel = parse_stat(h_savant.get("barrel_rate"))  # average ~7.5%
    barrel_points = min(25.0, h_barrel * 1.8)
    score += barrel_points
    
    # 3. Pitcher season HR vulnerability (max 20 points)
    p_hr9 = parse_stat(pitcher.get("home_runs_per_9"))  # average ~1.1
    hr9_points = min(20.0, p_hr9 * 11.0)
    score += hr9_points
    
    # 4. Pitcher Barrel% Allowed (max 15 points)
    p_savant = pitcher.get("savant", {})
    p_barrel_ag = parse_stat(p_savant.get("barrel_rate_against"))  # average ~7.5%
    barrel_ag_points = min(15.0, p_barrel_ag * 1.5)
    score += barrel_ag_points
    
    # 5. Platoon slugging splits
    hitter_hand_code = "vl" if pitcher_hand == "L" else "vr"
    hitter_splits = hitter.get("splits", {}).get(hitter_hand_code, {})
    hitter_slg = parse_stat(hitter_splits.get("slg"))
    if hitter_slg == 0.0:
        hitter_slg = parse_stat(hitter.get("slg"))
        
    if hitter_slg > 0.500:
        score += 10
    elif hitter_slg > 0.420:
        score += 5

    # 6. Stadium Park Factor (HR Multiplier - Lightweight)
    venue_lower = str(venue_name).lower()
    park_adj = 0
    high_parks = ["coors", "great american", "citizens bank", "guaranteed rate", "american family"]
    low_parks = ["oracle", "t-mobile", "loandepot", "comerica", "petco", "oakland coliseum", "ringcentral"]
    
    for park in high_parks:
        if park in venue_lower:
            park_adj = 4.0
            break
    for park in low_parks:
        if park in venue_lower:
            park_adj = -4.0
            break
    score += park_adj

    # 7. Pitcher Hard-Hit Rate Allowed (Statcast)
    p_hard_hit_ag = parse_stat(p_savant.get("hard_hit_rate_against"))
    if p_hard_hit_ag > 43.0:
        score += 4.0
    elif 0 < p_hard_hit_ag < 35.0:
        score -= 4.0

    # 8. HR Hitting Streak Adjustments
    if streak_data:
        current_hr_streak = streak_data.get("current_hr_streak", 0)
        last_hr_date = streak_data.get("last_hr_date")
        hits_in_last_5 = streak_data.get("hits_in_last_5", 0)
        
        if current_hr_streak >= 1:
            score += 4.0
        elif last_hr_date and last_hr_date != "None":
            try:
                last_dt = datetime.strptime(last_hr_date, "%Y-%m-%d")
                # Since datetime.today() might have a different year in tests, we compute difference dynamically
                # using the date from streak_data or default
                curr_dt = datetime.today()
                if abs((curr_dt - last_dt).days) <= 5:
                    score += 2.0
            except Exception:
                pass
                
        if hits_in_last_5 >= 4:
            score += 3.0

    # 9. Expected Team Runs Environment Adjustments
    if expected_team_runs >= 4.8:
        runs_diff = expected_team_runs - 4.4
        score += min(4.0, runs_diff * 1.0)
    elif expected_team_runs <= 4.0:
        runs_diff = 4.4 - expected_team_runs
        score -= min(4.0, runs_diff * 1.0)

    # 10. Opposing Bullpen Strength Adjustments
    if bullpen_era >= 4.60:
        score += 2.0
    elif bullpen_era <= 3.40:
        score -= 2.0
        
    return round(max(0.0, min(100.0, score)), 1)

def get_daily_leaderboards(all_games_data):
    """
    Generate player-level leaderboards for pitcher strikeouts (highest/lowest),
    batter hits/bases (highest), and batter home runs (highest).
    """
    import mlb_data
    
    pitchers_k_over = []
    pitchers_k_under = []
    batters_hits = []
    batters_hr = []
    
    for game in all_games_data:
        if not game:
            continue
            
        away_team = game["away_team"]
        home_team = game["home_team"]
        venue = game.get("venue_name", "TBD")
        game_id = game["game_id"]
        date_str = game.get("date", datetime.today().strftime('%Y-%m-%d'))
        
        # Starting Pitchers
        away_starter = next((p for p in game["pitchers"]["away"] if p["is_starter"]), None)
        home_starter = next((p for p in game["pitchers"]["home"] if p["is_starter"]), None)
        
        # Fallbacks
        if not away_starter and game["pitchers"]["away"]:
            away_starter = game["pitchers"]["away"][0]
        if not home_starter and game["pitchers"]["home"]:
            home_starter = game["pitchers"]["home"][0]
            
        # Precompute expected runs and bullpen stats for adjustments
        away_expected_runs = estimate_expected_runs("away", game)
        home_expected_runs = estimate_expected_runs("home", game)
        
        away_bp = get_bullpen_stats(game["pitchers"]["away"])
        home_bp = get_bullpen_stats(game["pitchers"]["home"])
            
        # 1. Pitcher Analysis
        if away_starter and home_starter:
            # Away Pitcher vs Home Lineup
            k_score, k_rat = analyze_pitcher_strikeouts(away_starter, game["players"]["home"])
            p_info = {
                "id": away_starter["id"],
                "game_id": game_id,
                "name": away_starter["name"],
                "team": away_team,
                "opponent": home_team,
                "k9": away_starter.get("strikeouts_per_9", "0.00"),
                "whip": away_starter.get("whip", "-.--"),
                "era": away_starter.get("era", "-.--"),
                "score": k_score,
                "under_score": round(100.0 - k_score, 1),
                "rationale": k_rat,
                "game": f"{away_team} @ {home_team}"
            }
            pitchers_k_over.append(p_info)
            pitchers_k_under.append(p_info)
            
            # Home Pitcher vs Away Lineup
            k_score, k_rat = analyze_pitcher_strikeouts(home_starter, game["players"]["away"])
            p_info = {
                "id": home_starter["id"],
                "game_id": game_id,
                "name": home_starter["name"],
                "team": home_team,
                "opponent": away_team,
                "k9": home_starter.get("strikeouts_per_9", "0.00"),
                "whip": home_starter.get("whip", "-.--"),
                "era": home_starter.get("era", "-.--"),
                "score": k_score,
                "under_score": round(100.0 - k_score, 1),
                "rationale": k_rat,
                "game": f"{away_team} @ {home_team}"
            }
            pitchers_k_over.append(p_info)
            pitchers_k_under.append(p_info)
            
            # 2. Hitter Analysis
            # Away batters vs Home Starter
            p_hand = home_starter.get("splits", {}).get("pitch_hand", "R")
            for hitter in game["players"]["away"]:
                if (hitter["is_starter"] or hitter.get("plate_appearances", 0) > 40) and hitter.get("plate_appearances", 0) >= 80:
                    try:
                        streak = mlb_data.get_player_recent_streak(hitter["id"], date_str)
                    except Exception:
                        streak = None
                        
                    hits_rating = calculate_matchup_rating(
                        hitter, home_starter, p_hand,
                        expected_team_runs=away_expected_runs,
                        bullpen_era=home_bp["era"],
                        streak_data=streak,
                        is_home=False
                    )
                    hr_rating = calculate_hr_rating(
                        hitter, home_starter, p_hand, venue_name=venue,
                        expected_team_runs=away_expected_runs,
                        bullpen_era=home_bp["era"],
                        streak_data=streak
                    )
                    
                    hitter_info = {
                        "id": hitter["id"],
                        "game_id": game_id,
                        "name": hitter["name"],
                        "team": away_team,
                        "opponent_pitcher": home_starter["name"],
                        "opponent_team": home_team,
                        "position": hitter["position"],
                        "avg": hitter["avg"],
                        "ops": hitter["ops"],
                        "home_runs": hitter["home_runs"],
                        "hits_rating": hits_rating,
                        "hr_rating": hr_rating,
                        "game": f"{away_team} @ {home_team}",
                        "savant_xwoba": hitter.get("savant", {}).get("xwoba", "TBD"),
                        "savant_barrel": hitter.get("savant", {}).get("barrel_rate", "TBD"),
                        "expected_runs": away_expected_runs,
                        "bullpen_era": home_bp["era"],
                        "hits": hitter.get("hits", 0),
                        "plate_appearances": hitter.get("plate_appearances", 0),
                        "games_played": hitter.get("games_played", 0)
                    }
                    batters_hits.append(hitter_info)
                    batters_hr.append(hitter_info)
                    
            # Home batters vs Away Starter
            p_hand = away_starter.get("splits", {}).get("pitch_hand", "R")
            for hitter in game["players"]["home"]:
                if (hitter["is_starter"] or hitter.get("plate_appearances", 0) > 40) and hitter.get("plate_appearances", 0) >= 80:
                    try:
                        streak = mlb_data.get_player_recent_streak(hitter["id"], date_str)
                    except Exception:
                        streak = None
                        
                    hits_rating = calculate_matchup_rating(
                        hitter, away_starter, p_hand,
                        expected_team_runs=home_expected_runs,
                        bullpen_era=away_bp["era"],
                        streak_data=streak,
                        is_home=True
                    )
                    hr_rating = calculate_hr_rating(
                        hitter, away_starter, p_hand, venue_name=venue,
                        expected_team_runs=home_expected_runs,
                        bullpen_era=away_bp["era"],
                        streak_data=streak
                    )
                    
                    hitter_info = {
                        "id": hitter["id"],
                        "game_id": game_id,
                        "name": hitter["name"],
                        "position": hitter["position"],
                        "team": home_team,
                        "opponent_pitcher": away_starter["name"],
                        "opponent_team": away_team,
                        "avg": hitter["avg"],
                        "ops": hitter["ops"],
                        "home_runs": hitter["home_runs"],
                        "hits_rating": hits_rating,
                        "hr_rating": hr_rating,
                        "game": f"{away_team} @ {home_team}",
                        "savant_xwoba": hitter.get("savant", {}).get("xwoba", "TBD"),
                        "savant_barrel": hitter.get("savant", {}).get("barrel_rate", "TBD"),
                        "expected_runs": home_expected_runs,
                        "bullpen_era": away_bp["era"],
                        "hits": hitter.get("hits", 0),
                        "plate_appearances": hitter.get("plate_appearances", 0),
                        "games_played": hitter.get("games_played", 0)
                    }
                    batters_hits.append(hitter_info)
                    batters_hr.append(hitter_info)
                    
    # Sort the leaderboards
    pitchers_k_over.sort(key=lambda x: x["score"], reverse=True)
    pitchers_k_under.sort(key=lambda x: x["under_score"], reverse=True)
    batters_hits.sort(key=lambda x: x["hits_rating"], reverse=True)
    batters_hr.sort(key=lambda x: x["hr_rating"], reverse=True)
    
    return {
        "pitchers_k_over": pitchers_k_over,
        "pitchers_k_under": pitchers_k_under,
        "batters_hits": batters_hits,
        "batters_hr": batters_hr
    }

def save_daily_picks(date_str, leaderboards):
    """
    Selects top picks from leaderboards and serializes them to saved_picks/{date_str}_picks.json.
    Enforces maximum of 2 hitters per team for Hits and HRs to ensure diversification.
    """
    os.makedirs("saved_picks", exist_ok=True)
    picks_path = os.path.join("saved_picks", f"{date_str}_picks.json")
    
    # Prevent overwriting completed results
    if os.path.exists(picks_path):
        try:
            with open(picks_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if existing.get("results_completed", False):
                    return
        except Exception:
            pass
            
    picks_data = {
        "date": date_str,
        "picks": {
            "pitchers_k_over": [],
            "pitchers_k_under": [],
            "batters_hits": [],
            "batters_hr": []
        },
        "results": {
            "pitchers_k_over": [],
            "pitchers_k_under": [],
            "batters_hits": [],
            "batters_hr": []
        },
        "results_completed": False
    }
    
    # 1. Pitchers K OVER (Top 5)
    for p in leaderboards.get("pitchers_k_over", [])[:5]:
        picks_data["picks"]["pitchers_k_over"].append({
            "id": p.get("id"),
            "name": p["name"],
            "team": p["team"],
            "opponent": p["opponent"],
            "score": p["score"],
            "k9": p["k9"],
            "game_id": p.get("game_id")
        })
        
    # 2. Pitchers K UNDER (Top 5)
    for p in leaderboards.get("pitchers_k_under", [])[:5]:
        picks_data["picks"]["pitchers_k_under"].append({
            "id": p.get("id"),
            "name": p["name"],
            "team": p["team"],
            "opponent": p["opponent"],
            "under_score": p["under_score"],
            "k9": p["k9"],
            "game_id": p.get("game_id")
        })
        
    # 3. Batters Hits (Top 10, max 2 per team)
    hits_team_counts = {}
    for b in leaderboards.get("batters_hits", []):
        if len(picks_data["picks"]["batters_hits"]) >= 10:
            break
        team = b["team"]
        count = hits_team_counts.get(team, 0)
        if count < 2:
            picks_data["picks"]["batters_hits"].append({
                "id": b["id"],
                "name": b["name"],
                "team": b["team"],
                "opponent_pitcher": b["opponent_pitcher"],
                "opponent_team": b["opponent_team"],
                "score": b["hits_rating"],
                "avg": b["avg"],
                "game_id": b.get("game_id")
            })
            hits_team_counts[team] = count + 1
        
    # 4. Batters HR (Top 10, max 2 per team)
    hr_team_counts = {}
    for b in leaderboards.get("batters_hr", []):
        if len(picks_data["picks"]["batters_hr"]) >= 10:
            break
        team = b["team"]
        count = hr_team_counts.get(team, 0)
        if count < 2:
            picks_data["picks"]["batters_hr"].append({
                "id": b["id"],
                "name": b["name"],
                "team": b["team"],
                "opponent_pitcher": b["opponent_pitcher"],
                "opponent_team": b["opponent_team"],
                "score": b["hr_rating"],
                "home_runs": b["home_runs"],
                "game_id": b.get("game_id")
            })
            hr_team_counts[team] = count + 1
        
    with open(picks_path, 'w', encoding='utf-8') as f:
        json.dump(picks_data, f, indent=2, ensure_ascii=False)

def load_and_track_picks(date_str):
    """
    Loads saved picks, queries boxscores for final stats, and merges them.
    Saves and returns the compiled results.
    """
    import mlb_data
    
    picks_path = os.path.join("saved_picks", f"{date_str}_picks.json")
    if not os.path.exists(picks_path):
        return None
        
    with open(picks_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    game_ids = set()
    for cat in ["pitchers_k_over", "pitchers_k_under", "batters_hits", "batters_hr"]:
        for item in data.get("picks", {}).get(cat, []):
            if item.get("game_id"):
                game_ids.add(item["game_id"])
                
    boxscores = {}
    for gid in game_ids:
        try:
            url = f"https://statsapi.mlb.com/api/v1/game/{gid}/boxscore"
            boxscore = mlb_data.fetch_json(url)
            if boxscore:
                boxscores[gid] = boxscore
        except Exception as e:
            print(f"Error fetching boxscore for game {gid}: {e}")
            
    results = {
        "pitchers_k_over": [],
        "pitchers_k_under": [],
        "batters_hits": [],
        "batters_hr": []
    }
    
    def find_player_stats(boxscore, player_id):
        if not boxscore or "teams" not in boxscore:
            return None
        for side in ["away", "home"]:
            players = boxscore["teams"][side].get("players", {})
            player_key = f"ID{player_id}"
            if player_key in players:
                return players[player_key]
        return None
        
    # 1. Pitchers K OVER
    for p in data["picks"].get("pitchers_k_over", []):
        gid = p.get("game_id")
        p_stats = find_player_stats(boxscores.get(gid), p["id"])
        
        actual_ks = 0
        actual_ip = "0.0"
        played = False
        if p_stats:
            p_details = p_stats.get("stats", {}).get("pitching", {})
            if p_details and p_details.get("gamesPlayed", 0) > 0:
                actual_ks = p_details.get("strikeOuts", 0)
                actual_ip = p_details.get("inningsPitched", "0.0")
                played = True
                
        results["pitchers_k_over"].append({
            **p,
            "actual_ks": actual_ks,
            "actual_ip": actual_ip,
            "played": played
        })
        
    # 2. Pitchers K UNDER
    for p in data["picks"].get("pitchers_k_under", []):
        gid = p.get("game_id")
        p_stats = find_player_stats(boxscores.get(gid), p["id"])
        
        actual_ks = 0
        actual_ip = "0.0"
        played = False
        if p_stats:
            p_details = p_stats.get("stats", {}).get("pitching", {})
            if p_details and p_details.get("gamesPlayed", 0) > 0:
                actual_ks = p_details.get("strikeOuts", 0)
                actual_ip = p_details.get("inningsPitched", "0.0")
                played = True
                
        results["pitchers_k_under"].append({
            **p,
            "actual_ks": actual_ks,
            "actual_ip": actual_ip,
            "played": played
        })
        
    # 3. Batters Hits
    for b in data["picks"].get("batters_hits", []):
        gid = b.get("game_id")
        b_stats = find_player_stats(boxscores.get(gid), b["id"])
        
        actual_hits = 0
        actual_hrs = 0
        actual_tbs = 0
        played = False
        if b_stats:
            b_details = b_stats.get("stats", {}).get("batting", {})
            if b_details and b_details.get("gamesPlayed", 0) > 0:
                actual_hits = b_details.get("hits", 0)
                actual_hrs = b_details.get("homeRuns", 0)
                actual_tbs = b_details.get("totalBases", 0)
                played = True
                
        results["batters_hits"].append({
            **b,
            "actual_hits": actual_hits,
            "actual_hrs": actual_hrs,
            "actual_tbs": actual_tbs,
            "played": played
        })
        
    # 4. Batters HR
    for b in data["picks"].get("batters_hr", []):
        gid = b.get("game_id")
        b_stats = find_player_stats(boxscores.get(gid), b["id"])
        
        actual_hits = 0
        actual_hrs = 0
        actual_tbs = 0
        played = False
        if b_stats:
            b_details = b_stats.get("stats", {}).get("batting", {})
            if b_details and b_details.get("gamesPlayed", 0) > 0:
                actual_hits = b_details.get("hits", 0)
                actual_hrs = b_details.get("homeRuns", 0)
                actual_tbs = b_details.get("totalBases", 0)
                played = True
                
        results["batters_hr"].append({
            **b,
            "actual_hits": actual_hits,
            "actual_hrs": actual_hrs,
            "actual_tbs": actual_tbs,
            "played": played
        })
        
    current_date_str = datetime.today().strftime('%Y-%m-%d')
    results_completed = (current_date_str > date_str)
    
    data["results"] = results
    data["results_completed"] = results_completed
    
    with open(picks_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return data

def catch_up_tracker_jobs():
    """
    Scans the last 7 days and runs missing jobs:
    - If a past day is past 12:00 PM and doesn't have picks cached, it generates them.
    - If a past day has picks but results are incomplete and we are past 8:00 AM the following day, it fetches boxscores.
    """
    import mlb_data
    
    os.makedirs("saved_picks", exist_ok=True)
    current_time = datetime.now()
    base_date = datetime.today()
    
    print("[Scheduler] Running self-healing catch-up check for past 7 days...")
    
    for i in range(7):
        target_date = base_date - timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        picks_path = os.path.join("saved_picks", f"{date_str}_picks.json")
        
        is_today = (date_str == base_date.strftime('%Y-%m-%d'))
        past_noon = current_time.hour >= 12
        
        # 1. Catch-up picks creation
        if not os.path.exists(picks_path):
            if not is_today or (is_today and past_noon):
                print(f"   [Scheduler] Creating picks file for {date_str}...")
                try:
                    games = mlb_data.get_today_games(date_str)
                    if games:
                        all_details = []
                        for g in games:
                            det = mlb_data.get_game_details(g["game_id"], date_str)
                            if det:
                                all_details.append(det)
                        if all_details:
                            lb = get_daily_leaderboards(all_details)
                            save_daily_picks(date_str, lb)
                            print(f"   [Scheduler] Saved picks successfully for {date_str}.")
                except Exception as e:
                    print(f"   [Scheduler] Error saving picks for {date_str}: {e}")
                    
        # 2. Catch-up results compilation
        if os.path.exists(picks_path):
            try:
                with open(picks_path, 'r', encoding='utf-8') as f:
                    picks_data = json.load(f)
            except Exception:
                picks_data = {}
                
            results_completed = picks_data.get("results_completed", False)
            
            if not is_today and not results_completed:
                is_yesterday = (date_str == (base_date - timedelta(days=1)).strftime('%Y-%m-%d'))
                past_eight_am = current_time.hour >= 8
                
                if not is_yesterday or (is_yesterday and past_eight_am):
                    print(f"   [Scheduler] Compiling results for {date_str}...")
                    try:
                        load_and_track_picks(date_str)
                        print(f"   [Scheduler] Saved results successfully for {date_str}.")
                    except Exception as e:
                        print(f"   [Scheduler] Error fetching results for {date_str}: {e}")

def get_under_regression_candidates(yesterday_date_str, today_games_details, today_leaderboards, min_hits=2, min_hrs=1):
    """
    Identifies hitters who recorded >= min_hits hits or >= min_hrs HR yesterday and are playing today.
    Cross-references them with today's starting matchups and Hits Scores to help
    users find potential UNDER on hits/bases regression candidates.
    """
    import mlb_data
    
    # 1. Fetch yesterday's games and boxscores to identify hot batters
    yesterday_games = mlb_data.get_today_games(yesterday_date_str)
    if not yesterday_games:
        return []
        
    hot_batters = {}
    for g in yesterday_games:
        gid = g["game_id"]
        url = f"https://statsapi.mlb.com/api/v1/game/{gid}/boxscore"
        try:
            boxscore = mlb_data.fetch_json(url)
            if not boxscore or "teams" not in boxscore:
                continue
            for side in ["away", "home"]:
                team_name = boxscore["teams"][side]["team"].get("name")
                players = boxscore["teams"][side].get("players", {})
                for p_key, p_val in players.items():
                    person = p_val.get("person", {})
                    name = person.get("fullName")
                    p_id = person.get("id")
                    batting_stats = p_val.get("stats", {}).get("batting", {})
                    if batting_stats and batting_stats.get("gamesPlayed", 0) > 0:
                        hits = batting_stats.get("hits", 0)
                        hrs = batting_stats.get("homeRuns", 0)
                        tbs = batting_stats.get("totalBases", 0)
                        ab = batting_stats.get("atBats", 0)
                        if hits >= min_hits or hrs >= min_hrs:
                            hot_batters[p_id] = {
                                "name": name,
                                "id": p_id,
                                "team": team_name,
                                "yesterday_stat": f"{hits} H ({ab} AB), {hrs} HR ({tbs} TB)"
                            }
        except Exception:
            pass
            
    # 2. Cross-reference hot batters with today's matchups and leaderboards
    candidates = []
    today_hitters = {}
    for game in today_games_details:
        if not game:
            continue
        away_starter = next((p for p in game["pitchers"]["away"] if p["is_starter"]), None) or (game["pitchers"]["away"][0] if game["pitchers"]["away"] else None)
        home_starter = next((p for p in game["pitchers"]["home"] if p["is_starter"]), None) or (game["pitchers"]["home"][0] if game["pitchers"]["home"] else None)
        
        for side in ["away", "home"]:
            opp_starter_name = home_starter["name"] if side == "away" else away_starter["name"] if away_starter else "TBD"
            opp_team = game["home_team"] if side == "away" else game["away_team"]
            for p in game["players"][side]:
                today_hitters[p["id"]] = {
                    "opponent_pitcher": opp_starter_name,
                    "opponent_team": opp_team,
                    "game": f"{game['away_team']} @ {game['home_team']}"
                }
                
    today_scores = {b["id"]: b for b in today_leaderboards.get("batters_hits", [])}
    
    for p_id, b_info in hot_batters.items():
        if p_id in today_hitters:
            th = today_hitters[p_id]
            ts = today_scores.get(p_id, {})
            score = ts.get("hits_rating", None)
            
            hits_val = ts.get("hits", 0)
            pa_val = ts.get("plate_appearances", 0)
            gp_val = ts.get("games_played", 0)
            
            hits_per_game = hits_val / gp_val if gp_val > 0 else 0.0
            hits_per_pa = hits_val / pa_val if pa_val > 0 else 0.0
            
            candidates.append({
                "id": p_id,
                "name": b_info["name"],
                "team": b_info["team"],
                "yesterday_stat": b_info["yesterday_stat"],
                "today_game": th["game"],
                "opponent_pitcher": th["opponent_pitcher"],
                "hits_score": score,
                "advantage": "🟢 Strong" if (isinstance(score, (int, float)) and score >= 75.0) else "🟡 Fair" if (isinstance(score, (int, float)) and score >= 65.0) else "🔴 Weak" if isinstance(score, (int, float)) else "N/A",
                "hits_per_game": hits_per_game,
                "hits_per_pa": hits_per_pa
            })
        else:
            candidates.append({
                "id": p_id,
                "name": b_info["name"],
                "team": b_info["team"],
                "yesterday_stat": b_info["yesterday_stat"],
                "today_game": "No Game Today",
                "opponent_pitcher": "N/A",
                "hits_score": "N/A",
                "advantage": "N/A",
                "hits_per_game": 0.0,
                "hits_per_pa": 0.0
            })
            
    # Sort candidates: show playing today first, then lowest hits score first (best under candidates!)
    def sort_key(c):
        playing = 1 if c["today_game"] != "No Game Today" else 0
        score_val = c["hits_score"] if isinstance(c["hits_score"], (int, float)) else 999.0
        return (-playing, score_val)
        
    candidates.sort(key=sort_key)
    return candidates

