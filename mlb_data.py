import os
import json
import urllib.request
import urllib.parse
from datetime import datetime
import pandas as pd

# Create cache directories
CACHE_DIR = "cache"
PLAYERS_CACHE_DIR = os.path.join(CACHE_DIR, "players")
SAVANT_CACHE_DIR = os.path.join(CACHE_DIR, "savant")

for d in [CACHE_DIR, PLAYERS_CACHE_DIR, SAVANT_CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

def fetch_json(url):
    """Utility to fetch JSON from MLB Stats API with User-Agent header."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return None

def get_today_games(date_str=None):
    """Fetch today's slate of games and starting pitchers."""
    if not date_str:
        date_str = datetime.today().strftime('%Y-%m-%d')
        
    cache_path = os.path.join(CACHE_DIR, f"{date_str}_games.json")
    
    # Check cache first
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
            
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher,decisions,linescore,venue"
    data = fetch_json(url)
    
    if not data or not data.get("dates"):
        return []
        
    games = data["dates"][0].get("games", [])
    game_list = []
    
    for game in games:
        game_id = game.get("gamePk")
        teams = game.get("teams", {})
        away = teams.get("away", {})
        home = teams.get("home", {})
        
        away_team = away.get("team", {})
        home_team = home.get("team", {})
        
        # Probable Pitchers
        away_pitcher = away.get("probablePitcher", {})
        home_pitcher = home.get("probablePitcher", {})
        
        status = game.get("status", {}).get("detailedState", "Scheduled")
        
        # Get line scores if available
        linescore = game.get("linescore", {})
        away_runs = linescore.get("teams", {}).get("away", {}).get("runs", 0)
        home_runs = linescore.get("teams", {}).get("home", {}).get("runs", 0)
        
        # Venue
        venue = game.get("venue", {})
        venue_name = venue.get("name", "TBD")
        
        game_list.append({
            "game_id": game_id,
            "date": date_str,
            "away_team_id": away_team.get("id"),
            "away_team": away_team.get("name"),
            "home_team_id": home_team.get("id"),
            "home_team": home_team.get("name"),
            "away_pitcher_id": away_pitcher.get("id"),
            "away_pitcher_name": away_pitcher.get("fullName", "TBD"),
            "home_pitcher_id": home_pitcher.get("id"),
            "home_pitcher_name": home_pitcher.get("fullName", "TBD"),
            "status": status,
            "away_runs": away_runs,
            "home_runs": home_runs,
            "venue_name": venue_name
        })
        
    # Cache the result
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(game_list, f, indent=2, ensure_ascii=False)
        
    return game_list

def fetch_player_season_stats_fallback(player_id, group="hitting"):
    """Fetch season stats directly from the people endpoint as a fallback."""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group={group}"
    data = fetch_json(url)
    if data and data.get("stats"):
        splits = data["stats"][0].get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    return {}

def get_player_splits_from_api(player_id, is_pitcher):
    """Fetch split stats for a player from MLB API."""
    group = "pitching" if is_pitcher else "hitting"
    url = f"https://statsapi.mlb.com/api/v1/people?personIds={player_id}&hydrate=stats(group=[{group}],type=[statSplits],sitCodes=[vl,vr])"
    data = fetch_json(url)
    
    splits_data = {"vl": {}, "vr": {}}
    if not data or not data.get("people"):
        return splits_data
        
    person = data["people"][0]
    
    # Store player side codes
    if is_pitcher:
        splits_data["pitch_hand"] = person.get("pitchHand", {}).get("code", "R")
    else:
        splits_data["bat_side"] = person.get("batSide", {}).get("code", "R")
        
    stats_list = person.get("stats", [])
    if not stats_list:
        return splits_data
        
    splits = stats_list[0].get("splits", [])
    for split in splits:
        code = split.get("split", {}).get("code")
        stat = split.get("stat", {})
        if code in ["vl", "vr"]:
            if is_pitcher:
                # Stats vs LHB/RHB
                splits_data[code] = {
                    "avg": stat.get("avg", ".000"),
                    "obp": stat.get("obp", ".000"),
                    "slg": stat.get("slg", ".000"),
                    "ops": stat.get("ops", ".000"),
                    "whip": stat.get("whip", 0.00),
                    "strikeOuts": stat.get("strikeOuts", 0),
                    "baseOnBalls": stat.get("baseOnBalls", 0),
                    "battersFaced": stat.get("battersFaced", 0),
                }
            else:
                # Hitter splits vs LHP/RHP
                splits_data[code] = {
                    "avg": stat.get("avg", ".000"),
                    "obp": stat.get("obp", ".000"),
                    "slg": stat.get("slg", ".000"),
                    "ops": stat.get("ops", ".000"),
                    "strikeOuts": stat.get("strikeOuts", 0),
                    "baseOnBalls": stat.get("baseOnBalls", 0),
                    "plateAppearances": stat.get("plateAppearances", 0),
                }
    return splits_data

def get_player_splits_cached(player_id, is_pitcher, date_str):
    """Fetch split stats, checking local player split cache directory first."""
    player_cache_dir = os.path.join(PLAYERS_CACHE_DIR, date_str)
    os.makedirs(player_cache_dir, exist_ok=True)
    
    cache_path = os.path.join(player_cache_dir, f"{player_id}.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
            
    splits = get_player_splits_from_api(player_id, is_pitcher)
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(splits, f, indent=2, ensure_ascii=False)
        
    return splits

def load_savant_leaderboards(season=2026):
    """Fetch and merge Statcast Expected Stats and Exit Velo leaderboards from pybaseball."""
    cache_path = os.path.join(SAVANT_CACHE_DIR, f"savant_leaderboards_{season}.json")
    
    # Try cache first
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
            
    print(f"Fetching Baseball Savant Leaderboards for season {season} via pybaseball...")
    savant_data = {"batters": {}, "pitchers": {}}
    
    try:
        from pybaseball import (
            statcast_batter_expected_stats,
            statcast_pitcher_expected_stats,
            statcast_batter_exitvelo_barrels,
            statcast_pitcher_exitvelo_barrels
        )
        
        # 1. Fetch expected stats
        # We catch exceptions to support seasons that might not have data yet (e.g. current season start)
        try:
            batters_exp = statcast_batter_expected_stats(season, minPA=50)
        except Exception as e:
            print(f"Could not load 2026 batters expected stats ({e}). Trying 2025.")
            batters_exp = statcast_batter_expected_stats(season - 1, minPA=50)
            
        try:
            pitchers_exp = statcast_pitcher_expected_stats(season, minPA=50)
        except Exception as e:
            print(f"Could not load 2026 pitchers expected stats ({e}). Trying 2025.")
            pitchers_exp = statcast_pitcher_expected_stats(season - 1, minPA=50)
            
        # 2. Fetch Exit Velo & Barrels
        try:
            batters_ev = statcast_batter_exitvelo_barrels(season, minBBE=30)
        except Exception as e:
            print(f"Could not load 2026 batters exit velo ({e}). Trying 2025.")
            batters_ev = statcast_batter_exitvelo_barrels(season - 1, minBBE=30)
            
        try:
            pitchers_ev = statcast_pitcher_exitvelo_barrels(season, minBBE=30)
        except Exception as e:
            print(f"Could not load 2026 pitchers exit velo ({e}). Trying 2025.")
            pitchers_ev = statcast_pitcher_exitvelo_barrels(season - 1, minBBE=30)
            
        # Process Batters
        if not batters_exp.empty:
            for _, row in batters_exp.iterrows():
                p_id = str(int(row['player_id']))
                savant_data["batters"][p_id] = {
                    "xwoba": row.get("est_woba", 0.0),
                    "xba": row.get("est_ba", 0.0),
                    "xslg": row.get("est_slg", 0.0),
                    "woba": row.get("woba", 0.0),
                    "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                }
                
        if not batters_ev.empty:
            for _, row in batters_ev.iterrows():
                p_id = str(int(row['player_id']))
                if p_id in savant_data["batters"]:
                    savant_data["batters"][p_id].update({
                        "avg_exit_velo": row.get("avg_hit_speed", 0.0),
                        "max_exit_velo": row.get("max_hit_speed", 0.0),
                        "barrel_rate": row.get("barrel_batted_rate", 0.0), # barrel% per batted ball
                        "hard_hit_rate": row.get("hard_hit_speed_pct", 0.0)
                    })
                else:
                    savant_data["batters"][p_id] = {
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "avg_exit_velo": row.get("avg_hit_speed", 0.0),
                        "max_exit_velo": row.get("max_hit_speed", 0.0),
                        "barrel_rate": row.get("barrel_batted_rate", 0.0),
                        "hard_hit_rate": row.get("hard_hit_speed_pct", 0.0)
                    }

        # Process Pitchers
        if not pitchers_exp.empty:
            for _, row in pitchers_exp.iterrows():
                p_id = str(int(row['player_id']))
                savant_data["pitchers"][p_id] = {
                    "xwoba_against": row.get("est_woba", 0.0),
                    "xba_against": row.get("est_ba", 0.0),
                    "xslg_against": row.get("est_slg", 0.0),
                    "woba_against": row.get("woba", 0.0),
                    "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                }
                
        if not pitchers_ev.empty:
            for _, row in pitchers_ev.iterrows():
                p_id = str(int(row['player_id']))
                if p_id in savant_data["pitchers"]:
                    savant_data["pitchers"][p_id].update({
                        "avg_exit_velo_against": row.get("avg_hit_speed", 0.0),
                        "barrel_rate_against": row.get("barrel_batted_rate", 0.0),
                        "hard_hit_rate_against": row.get("hard_hit_speed_pct", 0.0)
                    })
                else:
                    savant_data["pitchers"][p_id] = {
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "avg_exit_velo_against": row.get("avg_hit_speed", 0.0),
                        "barrel_rate_against": row.get("barrel_batted_rate", 0.0),
                        "hard_hit_rate_against": row.get("hard_hit_speed_pct", 0.0)
                    }

    except Exception as e:
        print(f"Error loading pybaseball leaderboards: {e}")
        
    # Save cache
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(savant_data, f, indent=2, ensure_ascii=False)
        
    return savant_data

def get_game_details(game_id, date_str=None):
    """Fetch complete game dataset including rosters, season stats, splits, and Baseball Savant metrics."""
    if not date_str:
        date_str = datetime.today().strftime('%Y-%m-%d')
        
    game_cache_path = os.path.join(CACHE_DIR, f"{date_str}_game_{game_id}.json")
    
    # Try cache first
    if os.path.exists(game_cache_path):
        try:
            with open(game_cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if cached_data:
                    away_batters = cached_data.get("players", {}).get("away", [])
                    home_batters = cached_data.get("players", {}).get("home", [])
                    status = cached_data.get("status", "Scheduled")
                    
                    # If the cache file has players OR the game is already final, return it
                    if (len(away_batters) > 0 or len(home_batters) > 0) or status == "Final":
                        return cached_data
        except Exception:
            pass
            
    # Load Savant stats (usually cached on disk)
    savant_stats = load_savant_leaderboards(datetime.strptime(date_str, '%Y-%m-%d').year)
    
    # Fetch boxscore
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    boxscore = fetch_json(url)
    if not boxscore or "teams" not in boxscore:
        return None
        
    schedule = get_today_games(date_str)
    game_meta = next((g for g in schedule if g["game_id"] == game_id), {})
    
    game_data = {
        "game_id": game_id,
        "date": date_str,
        "away_team": game_meta.get("away_team", boxscore["teams"]["away"]["team"].get("name")),
        "home_team": game_meta.get("home_team", boxscore["teams"]["home"]["team"].get("name")),
        "away_pitcher": game_meta.get("away_pitcher_name", "TBD"),
        "home_pitcher": game_meta.get("home_pitcher_name", "TBD"),
        "away_pitcher_id": game_meta.get("away_pitcher_id"),
        "home_pitcher_id": game_meta.get("home_pitcher_id"),
        "status": game_meta.get("status", "Scheduled"),
        "venue_name": game_meta.get("venue_name", "TBD"),
        "players": {"away": [], "home": []},
        "pitchers": {"away": [], "home": []}
    }
    
    # Process both teams
    for side in ["away", "home"]:
        team_players = boxscore["teams"][side].get("players", {})
        team_batters_ids = boxscore["teams"][side].get("batters", [])
        
        # Resolve starting pitcher ID from schedule if boxscore lists TBD
        starting_pitcher_id = game_data[f"{side}_pitcher_id"]
        
        for player_key, player_obj in team_players.items():
            person = player_obj.get("person", {})
            p_id = person.get("id")
            name = person.get("fullName")
            pos = player_obj.get("position", {})
            pos_code = pos.get("code")
            pos_type = pos.get("type")
            
            # 1. Standard Pitcher stats
            if pos_type == "Pitcher" or p_id == starting_pitcher_id:
                pitch_stats = player_obj.get("seasonStats", {}).get("pitching", {})
                if (not pitch_stats or pitch_stats.get("gamesPlayed", 0) == 0) and p_id:
                    cache_dir_peop = os.path.join(PLAYERS_CACHE_DIR, f"{date_str}_season_stats_pitch")
                    os.makedirs(cache_dir_peop, exist_ok=True)
                    peop_cache_path = os.path.join(cache_dir_peop, f"{p_id}.json")
                    if os.path.exists(peop_cache_path):
                        try:
                            with open(peop_cache_path, 'r', encoding='utf-8') as f:
                                pitch_stats = json.load(f)
                        except Exception:
                            pitch_stats = {}
                    else:
                        pitch_stats = fetch_player_season_stats_fallback(p_id, "pitching")
                        with open(peop_cache_path, 'w', encoding='utf-8') as f:
                            json.dump(pitch_stats, f, indent=2, ensure_ascii=False)
                            
                if not pitch_stats and p_id == starting_pitcher_id:
                    pitch_stats = {"era": "-.--", "whip": "-.--", "gamesPlayed": 0, "strikeOuts": 0}
                
                if pitch_stats:
                    # Hydrate with splits
                    splits = get_player_splits_cached(p_id, is_pitcher=True, date_str=date_str)
                    # Hydrate with Savant
                    savant = savant_stats["pitchers"].get(str(p_id), {})
                    
                    pitcher_info = {
                        "id": p_id,
                        "name": name,
                        "position": pos.get("name"),
                        "is_starter": p_id == starting_pitcher_id,
                        "era": pitch_stats.get("era", "-.--"),
                        "whip": pitch_stats.get("whip", "-.--"),
                        "avg_allowed": pitch_stats.get("avg", ".250"),
                        "innings_pitched": pitch_stats.get("inningsPitched", "0.0"),
                        "strikeouts": pitch_stats.get("strikeOuts", 0),
                        "walks": pitch_stats.get("baseOnBalls", 0),
                        "games_played": pitch_stats.get("gamesPlayed", 0),
                        "games_started": pitch_stats.get("gamesStarted", 0),
                        "strikeouts_per_9": pitch_stats.get("strikeoutsPer9Inn", "0.00"),
                        "walks_per_9": pitch_stats.get("walksPer9Inn", "0.00"),
                        "splits": splits,
                        "savant": savant
                    }
                    game_data["pitchers"][side].append(pitcher_info)
                    
                    # Update starting pitcher details if missing
                    if pitcher_info["is_starter"]:
                        game_data[f"{side}_pitcher_name"] = name
            
            # 2. Standard Batter stats
            bat_stats = player_obj.get("seasonStats", {}).get("batting", {})
            if (not bat_stats or bat_stats.get("gamesPlayed", 0) == 0) and pos_type != "Pitcher" and p_id:
                cache_dir_peop = os.path.join(PLAYERS_CACHE_DIR, f"{date_str}_season_stats_hit")
                os.makedirs(cache_dir_peop, exist_ok=True)
                peop_cache_path = os.path.join(cache_dir_peop, f"{p_id}.json")
                if os.path.exists(peop_cache_path):
                    try:
                        with open(peop_cache_path, 'r', encoding='utf-8') as f:
                            bat_stats = json.load(f)
                    except Exception:
                        bat_stats = {}
                else:
                    bat_stats = fetch_player_season_stats_fallback(p_id, "hitting")
                    with open(peop_cache_path, 'w', encoding='utf-8') as f:
                        json.dump(bat_stats, f, indent=2, ensure_ascii=False)
                        
            if bat_stats and bat_stats.get("gamesPlayed", 0) > 0:
                is_starting_hitter = p_id in team_batters_ids
                if not team_batters_ids:
                    try:
                        pa = float(bat_stats.get("plateAppearances", bat_stats.get("plate_appearances", 0)))
                    except Exception:
                        pa = 0
                    is_starting_hitter = pa > 40
                
                # Fetch splits (only fetch splits for starting batters to keep it fast)
                splits = {}
                if is_starting_hitter:
                    splits = get_player_splits_cached(p_id, is_pitcher=False, date_str=date_str)
                    
                savant = savant_stats["batters"].get(str(p_id), {})
                
                # Resolve batting order (1-indexed)
                batting_order = -1
                if is_starting_hitter and team_batters_ids:
                    try:
                        batting_order = team_batters_ids.index(p_id) + 1
                    except ValueError:
                        pass
                
                batter_info = {
                    "id": p_id,
                    "name": name,
                    "position": pos.get("name"),
                    "is_starter": is_starting_hitter,
                    "batting_order": batting_order,
                    "avg": bat_stats.get("avg", ".000"),
                    "obp": bat_stats.get("obp", ".000"),
                    "slg": bat_stats.get("slg", ".000"),
                    "ops": bat_stats.get("ops", ".000"),
                    "hits": bat_stats.get("hits", 0),
                    "home_runs": bat_stats.get("homeRuns", 0),
                    "rbi": bat_stats.get("rbi", 0),
                    "strikeouts": bat_stats.get("strikeOuts", 0),
                    "walks": bat_stats.get("baseOnBalls", 0),
                    "plate_appearances": bat_stats.get("plateAppearances", 0),
                    "games_played": bat_stats.get("gamesPlayed", 0),
                    "splits": splits,
                    "savant": savant
                }
                game_data["players"][side].append(batter_info)
                
    # Cache game detail
    with open(game_cache_path, 'w', encoding='utf-8') as f:
        json.dump(game_data, f, indent=2, ensure_ascii=False)
        
    return game_data

def get_player_last_hr_date(player_id, date_str):
    """Retrieve the date of the player's most recent home run (caching daily)."""
    # Simply wrap the new rich streak calculator to ensure backwards compatibility
    streak_data = get_player_recent_streak(player_id, date_str)
    return streak_data.get("last_hr_date")

def get_player_recent_streak(player_id, date_str):
    """Retrieve player's recent hitting stats (hits in last 5 games, active hit/HR streaks, last HR date)."""
    year = datetime.strptime(date_str, '%Y-%m-%d').year
    
    cache_dir = os.path.join(CACHE_DIR, "player_streaks", date_str)
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{player_id}.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
            
    # Default values
    streak_data = {
        "hits_in_last_5": 0,
        "current_hit_streak": 0,
        "current_hr_streak": 0,
        "last_hr_date": "None"
    }
    
    # Fetch gameLog for current year
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={year}"
    data = fetch_json(url)
    
    splits = []
    if data and data.get("stats"):
        splits = data["stats"][0].get("splits", [])
        
    # If no games played this season, try previous year for last HR date
    if not splits:
        url_prev = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={year-1}"
        data_prev = fetch_json(url_prev)
        if data_prev and data_prev.get("stats"):
            prev_splits = data_prev["stats"][0].get("splits", [])
            for split in reversed(prev_splits):
                stat = split.get("stat", {})
                if stat.get("homeRuns", 0) > 0:
                    streak_data["last_hr_date"] = split.get("date")
                    break
            # Cache and return since there are no active streaks for this year
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(streak_data, f, indent=2, ensure_ascii=False)
            return streak_data

    # Process splits (splits list is chronological: oldest to newest)
    last_5_splits = splits[-5:]
    hits_in_last_5 = sum(1 for split in last_5_splits if split.get("stat", {}).get("hits", 0) > 0)
    streak_data["hits_in_last_5"] = hits_in_last_5
    
    # Calculate active hit streak by walking backwards
    current_hit_streak = 0
    for split in reversed(splits):
        if split.get("stat", {}).get("hits", 0) > 0:
            current_hit_streak += 1
        else:
            break
    streak_data["current_hit_streak"] = current_hit_streak
    
    # Calculate active HR streak by walking backwards
    current_hr_streak = 0
    for split in reversed(splits):
        if split.get("stat", {}).get("homeRuns", 0) > 0:
            current_hr_streak += 1
        else:
            break
    streak_data["current_hr_streak"] = current_hr_streak
    
    # Find last HR date
    last_hr_date = None
    for split in reversed(splits):
        if split.get("stat", {}).get("homeRuns", 0) > 0:
            last_hr_date = split.get("date")
            break
            
    # If not found in current season, check previous season
    if not last_hr_date:
        url_prev = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={year-1}"
        data_prev = fetch_json(url_prev)
        if data_prev and data_prev.get("stats"):
            prev_splits = data_prev["stats"][0].get("splits", [])
            for split in reversed(prev_splits):
                if split.get("stat", {}).get("homeRuns", 0) > 0:
                    last_hr_date = split.get("date")
                    break
                    
    streak_data["last_hr_date"] = last_hr_date or "None"
    
    # Cache result
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(streak_data, f, indent=2, ensure_ascii=False)
        
    return streak_data
