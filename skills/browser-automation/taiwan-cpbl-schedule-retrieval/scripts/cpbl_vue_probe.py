import sys
import json
import argparse
from playwright.sync_api import sync_playwright

def probe_cpbl_schedule(target_date=None, live_only=False):
    """
    Launches headless Chrome, navigates to CPBL homepage / schedule,
    and extracts live game states, real-time scores, and inning details.
    """
    homepage_games = []
    gamedatas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            nonlocal gamedatas
            if "getgamedatas" in response.url and response.status == 200:
                try:
                    data = response.json()
                    if data.get("Success") and "GameDatas" in data:
                        gamedatas = json.loads(data["GameDatas"])
                except Exception:
                    pass

        page.on("response", handle_response)

        # 1. First probe homepage for real-time live scores & CurtBatting
        try:
            page.goto("https://cpbl.com.tw/", timeout=30000)
            page.wait_for_timeout(2000)
            g_a = page.evaluate("typeof app !== 'undefined' && app.GameADetail ? app.GameADetail : null")
            g_d = page.evaluate("typeof app !== 'undefined' && app.GameDDetail ? app.GameDDetail : null")
            if g_a:
                homepage_games.extend(g_a)
            if g_d:
                homepage_games.extend(g_d)
        except Exception as e:
            sys.stderr.write(f"Warning fetching homepage live data: {e}\n")

        # 2. Probe schedule page if historical/future date requested or getgamedatas needed
        if target_date or not homepage_games:
            try:
                page.goto("https://cpbl.com.tw/schedule", timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                sys.stderr.write(f"Warning fetching schedule page: {e}\n")

        browser.close()

    # Process homepage live state first if available
    games_source = homepage_games if homepage_games else gamedatas

    parsed_games = []
    for g in games_source:
        game_date = g.get("GameDate", "")[:10]
        if target_date and not game_date.startswith(target_date):
            continue

        v_score = g.get("VisitingTotalScore") if g.get("VisitingTotalScore") is not None else g.get("VisitingScore", 0)
        h_score = g.get("HomeTotalScore") if g.get("HomeTotalScore") is not None else g.get("HomeScore", 0)
        curt = g.get("CurtBatting") or {}

        inning_seq = curt.get("InningSeq")
        visiting_home_type = curt.get("VisitingHomeType")  # "1" = top (上), "2" = bottom (下)
        inning_str = ""
        if inning_seq:
            half_str = "上" if visiting_home_type == "1" else "下"
            inning_str = f"{inning_seq}局{half_str}"

        parsed_games.append({
            "game_sno": g.get("GameSno"),
            "date": game_date,
            "field": g.get("FieldAbbe"),
            "game_status": g.get("GameStatus"),  # 1: scheduled, 2: in-progress, 6: cancelled/postponed
            "visiting_team": g.get("VisitingTeamName"),
            "visiting_score": v_score,
            "home_team": g.get("HomeTeamName"),
            "home_score": h_score,
            "inning": inning_str,
            "out_cnt": curt.get("OutCnt"),
            "hitter": curt.get("HitterName"),
            "pitcher": curt.get("PitcherName"),
            "strike_cnt": curt.get("StrikeCnt"),
            "ball_cnt": curt.get("BallCnt"),
            "bases": {
                "1b": bool(curt.get("FirstBase")),
                "2b": bool(curt.get("SecondBase")),
                "3b": bool(curt.get("ThirdBase")),
            },
            "visiting_starter": g.get("VisitingFirstMover"),
            "home_starter": g.get("HomeFirstMover"),
        })

    if live_only:
        parsed_games = [g for g in parsed_games if g.get("game_status") == 2]

    return {"games": parsed_games, "total_found": len(parsed_games)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract CPBL live scores and game schedules via Playwright.")
    parser.add_argument("-d", "--date", type=str, help="Target date in YYYY-MM-DD format (e.g., 2026-08-25)")
    parser.add_argument("--live", action="store_true", help="Only return games currently in progress")
    args = parser.parse_args()

    try:
        result = probe_cpbl_schedule(target_date=args.date, live_only=args.live)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.exit(1)
