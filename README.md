# ⚾ MLB Prop Analytics & Parlay AI

An interactive sports betting analytics dashboard and AI agent that pulls Major League Baseball (MLB) schedules, active player statistics, situational platoon splits, and Baseball Savant Statcast expected metrics to build player-level leaderboards and suggest correlated parlays.

---

## Features

1. **🏟️ Today's Matchups**: View today's slate of games, compare starting pitchers side-by-side (including their LHP/RHP splits), and display batter matchup rating cards.
2. **🎯 Player Prop Targets**: View ranked list leaderboards for specific sports betting props:
   - **Strikeouts OVER Candidates** (Dominant starting pitchers facing high strikeout lineups).
   - **Strikeouts UNDER Candidates** (Low-strikeout starters facing disciplined lineups).
   - **Hitter Hits & Bases Candidates** (Hitters with favorable platoon splits and high Statcast xwOBA).
   - **Hitter Home Run Candidates** (High power-contact hitters facing home run-prone starting pitchers, using a custom Statcast barrel rate probability model).
3. **📈 Correlated Parlay Suggestions**: Displays daily parlay slips matching correlated game conditions (e.g. *Starting Pitcher Ks OVER* + *Opponent Team Total Runs UNDER*) with detailed analytical rationales.
4. **💬 AI Betting Assistant**: An interactive chat sidebar to ask questions about player stats, matchup matrices, and parlay strategies. Supports Anthropic Claude, Google Gemini, and a rule-based mathematical fallback.

---

## Local Setup

### Prerequisites
- **Python 3.10+** (This project was built and verified on Python 3.12.10)

### 1. Install Dependencies
Navigate to your workspace directory and install the required python packages:
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys (Optional)
To enable conversational AI chat, choose one of these methods:
- **Inside the App**: Type or paste your Claude or Gemini API Key directly into the **Key Configuration panel** in the application's sidebar.
- **Via environment file**: Rename `.env.template` to `.env` and fill in your keys:
  ```env
  GEMINI_API_KEY=your_gemini_api_key
  ANTHROPIC_API_KEY=your_anthropic_api_key
  ```
*If no keys are provided, the chat panel switches to **Fallback Mode** where you can still query stats and parlays using basic keywords.*

### 3. Run the Dashboard
Start the local Streamlit server:
```bash
python -m streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your web browser.

---

## Publishing to Streamlit Community Cloud (Option 1)

When you are ready to publish this dashboard so a friend can access it online for free:

1. **Push to GitHub**:
   - Create a repository on GitHub (public or private).
   - Push your workspace folder to the repository. The `.gitignore` file will automatically prevent your private `.env` and cache folders from being uploaded.
2. **Deploy on Streamlit Cloud**:
   - Log in at [share.streamlit.io](https://share.streamlit.io/) with your GitHub account.
   - Click **"New app"**.
   - Input your repository path, set branch to `main`, and set the file path to `app.py`.
   - Click **"Deploy"**.
3. **Configure Secrets (Optional)**:
   - If you want the app to automatically use your API keys rather than making your friend paste theirs, go to the app settings in the Streamlit Cloud dashboard, open the **"Secrets"** tab, and add your keys in TOML format:
     ```toml
     GEMINI_API_KEY = "your-api-key"
     ```
4. **Share the Link**: Once the compilation completes, Streamlit will provide you with a public link (e.g., `your-app.streamlit.app`) to share.
