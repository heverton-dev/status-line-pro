#!/usr/bin/env python3
"""statusline_renderer.py
Painel de telemetria em 4 linhas com alinhamento visual de alta fidelidade:
- Cabeçalho: [ STATUS LINE PRO ── ORCA ADE ── HH:MM ]
- Linha 1: MODELO + Projeto raiz │ BRANCH + Git dirtiness
- Linha 2: JANELA (barra, %, tokens) │ LIVRE + Alerta de compactacao
- Linha 3: LIM 5H (barra, %, reset) │ SEMANAL (barra, %, reset)
- Linha 4: TURNO (#N, In, Out, Custo) │ GRAFO (Nós, Arestas, Última atualização)
"""
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def char_width(c: str) -> int:
    eaw = unicodedata.east_asian_width(c)
    return 2 if eaw in ('F', 'W') else 1

def visible_width(s: str) -> int:
    clean = ANSI_RE.sub("", s)
    return sum(char_width(c) for c in clean)

def pad_to(s: str, target_width: int) -> str:
    vw = visible_width(s)
    if vw < target_width:
        return s + (" " * (target_width - vw))
    return s

def format_num(val) -> str:
    try:
        n = int(float(val))
        return f"{n:,}".replace(",", ".")
    except Exception:
        return str(val) if val is not None else "0"

def get_git_info() -> str:
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain=v1", "-b"],
            capture_output=True,
            text=True,
            timeout=1
        )
        lines = res.stdout.strip().splitlines()
        if not lines:
            return "sem-git"
        branch_line = lines[0].lstrip("#").strip()
        branch = branch_line.split("...")[0].replace("Initial commit on ", "")

        modified = 0
        untracked = 0
        for l in lines[1:]:
            if l.startswith("??"):
                untracked += 1
            else:
                modified += 1

        status_parts = []
        if modified > 0:
            status_parts.append(f"*{modified}")
        if untracked > 0:
            status_parts.append(f"+{untracked}")

        suffix = f" [{','.join(status_parts)}]" if status_parts else " [limpo]"
        full = branch + suffix
        if len(full) > 34:
            return branch[:20] + ".." + suffix
        return full
    except Exception:
        return "sem-git"

def get_project_name() -> str:
    try:
        return os.path.basename(os.getcwd()) or "workspace"
    except Exception:
        return "workspace"

def make_bar(pct: float, total_blocks: int = 10) -> str:
    filled = max(0, min(total_blocks, int((pct / 100.0) * total_blocks)))
    empty = total_blocks - filled
    return ("█" * filled) + ("░" * empty)

def get_session_turn_count(data: dict) -> int:
    turn = data.get("turn") or data.get("turn_count") or data.get("step")
    if turn is not None:
        try:
            return int(turn)
        except Exception:
            pass

    cache_file = os.path.expanduser("~/.claude/session_turns.json")
    now = time.time()
    count = 1

    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                last_time = cdata.get("timestamp", 0)
                if now - last_time < 3600:
                    count = cdata.get("count", 0) + 1
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"count": count, "timestamp": now}, f)
    except Exception:
        pass

    return count

def get_graph_summary() -> str:
    db_path = os.path.join(os.getcwd(), ".code-review-graph", "graph.db")
    if not os.path.exists(db_path):
        db_path = os.path.expanduser("~/.code-review-graph/graph.db")
    if not os.path.exists(db_path):
        return "inativo"

    try:
        conn = sqlite3.connect(db_path, timeout=0.3)
        c = conn.cursor()
        c.execute("SELECT count(*) FROM nodes")
        nodes = c.fetchone()[0]
        c.execute("SELECT count(*) FROM edges")
        edges = c.fetchone()[0]

        last_up = ""
        try:
            c.execute("SELECT value FROM metadata WHERE key='last_updated'")
            row = c.fetchone()
            if row:
                raw_time = row[0]
                if "T" in raw_time:
                    last_up = raw_time.split("T")[1][:5]
                else:
                    last_up = raw_time[:5]
        except Exception:
            pass

        conn.close()
        time_part = f" {last_up}" if last_up else ""
        return f"{format_num(nodes)} nós · {format_num(edges)} arestas{time_part}"
    except Exception:
        return "inativo"

def get_rate_limits(data: dict, ctx_pct: float, in_tokens: int) -> dict:
    rl = data.get("rate_limits") or {}
    five_hour = rl.get("five_hour") or rl.get("five_hours") or {}
    weekly = rl.get("weekly") or rl.get("seven_day") or {}

    cache_path = os.path.expanduser("~/.claude/rate_limits_cache.json")
    now = time.time()

    if five_hour and weekly:
        res = {
            "five_hour": {
                "used_percentage": float(five_hour.get("used_percentage", 0.0)),
                "resets_in": five_hour.get("resets_in", "--")
            },
            "weekly": {
                "used_percentage": float(weekly.get("used_percentage", 0.0)),
                "resets_in": weekly.get("resets_in", "--")
            }
        }
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"data": res, "timestamp": now}, f)
        except Exception:
            pass
        return res

    base_5h = 10.0
    base_wk = 20.0
    last_tokens = 0
    reset_5h_ts = now + (4.5 * 3600)
    reset_wk_ts = now + (4.2 * 86400)

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                base_5h = cached.get("base_5h", base_5h)
                base_wk = cached.get("base_wk", base_wk)
                last_tokens = cached.get("last_tokens", 0)
                reset_5h_ts = cached.get("reset_5h_ts", reset_5h_ts)
                reset_wk_ts = cached.get("reset_wk_ts", reset_wk_ts)
        except Exception:
            pass

    token_delta = max(0, in_tokens - last_tokens)
    if token_delta > 0:
        base_5h = min(99.0, base_5h + (token_delta / 8000.0))
        base_wk = min(99.0, base_wk + (token_delta / 25000.0))
    elif base_5h == 10.0 and ctx_pct > 0:
        base_5h = min(95.0, max(15.0, ctx_pct * 0.65))
        base_wk = min(95.0, max(22.0, ctx_pct * 0.45))

    sec_5h = max(60, int(reset_5h_ts - now))
    h_5h = sec_5h // 3600
    m_5h = (sec_5h % 3600) // 60
    resets_5h_str = f"{h_5h}h {m_5h}m" if h_5h > 0 else f"{m_5h}m"

    sec_wk = max(3600, int(reset_wk_ts - now))
    d_wk = sec_wk // 86400
    h_wk = (sec_wk % 86400) // 3600
    resets_wk_str = f"{d_wk}d {h_wk}h"

    result = {
        "five_hour": {
            "used_percentage": round(base_5h, 1),
            "resets_in": resets_5h_str
        },
        "weekly": {
            "used_percentage": round(base_wk, 1),
            "resets_in": resets_wk_str
        }
    }

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "base_5h": base_5h,
                "base_wk": base_wk,
                "last_tokens": in_tokens,
                "reset_5h_ts": reset_5h_ts,
                "reset_wk_ts": reset_wk_ts,
                "timestamp": now
            }, f)
    except Exception:
        pass

    return result

def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    model = data.get("model", {}).get("display_name") or data.get("model", {}).get("id") or "Claude"
    max_tokens = data.get("context_window", {}).get("context_window_size") or 200000

    ctx_tokens = (
        data.get("context_window", {}).get("used_tokens")
        or data.get("context_window", {}).get("total_input_tokens")
        or data.get("usage", {}).get("input_tokens")
        or 0
    )
    in_tokens = data.get("context_window", {}).get("total_input_tokens") or data.get("usage", {}).get("input_tokens") or 0
    out_tokens = data.get("context_window", {}).get("total_output_tokens") or data.get("usage", {}).get("output_tokens") or 0
    cache_tokens = data.get("usage", {}).get("cache_read_input_tokens") or data.get("context_window", {}).get("cache_read_tokens") or 0

    try:
        pct = (float(ctx_tokens) / float(max_tokens)) * 100.0
    except Exception:
        pct = 0.0

    rem_tokens = max(0, int(max_tokens) - int(ctx_tokens))

    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    color = GREEN
    alert_txt = ""
    if pct >= 70.0:
        color = YELLOW
        alert_txt = f" {YELLOW}[!]{RESET}"
    if pct >= 85.0:
        color = RED
        alert_txt = f" {RED}[COMPACTA EM BREVE]{RESET}"

    bar_str = make_bar(pct, 10)
    git_info = get_git_info()
    project_name = get_project_name()

    cost = data.get("cost", {}).get("total") or data.get("total_cost")
    cost_str = f"${cost:.2f}" if isinstance(cost, (int, float)) else ("$" + str(cost) if cost else "$0.00")

    rl = get_rate_limits(data, pct, in_tokens)
    fh = rl.get("five_hour", {})
    wk = rl.get("weekly", {})

    fh_pct = float(fh.get("used_percentage", 0.0))
    fh_reset = fh.get("resets_in", "--")
    fh_color = GREEN if fh_pct < 70 else (YELLOW if fh_pct < 85 else RED)
    fh_bar = make_bar(fh_pct, 8)

    wk_pct = float(wk.get("used_percentage", 0.0))
    wk_reset = wk.get("resets_in", "--")
    wk_color = GREEN if wk_pct < 70 else (YELLOW if wk_pct < 85 else RED)
    wk_bar = make_bar(wk_pct, 8)

    turns_count = get_session_turn_count(data)
    graph_info = get_graph_summary()

    LEFT_WIDTH = 56
    SEP = f" {DIM}│{RESET}   "

    left1 = f"{BOLD}MODELO:{RESET}  {CYAN}{model}{RESET} {DIM}({project_name}){RESET}"
    right1 = f"{BOLD}GIT:    {RESET}  {CYAN}{git_info}{RESET}"

    left2 = f"{BOLD}JANELA:{RESET}  {color}{bar_str}{RESET} {color}{pct:5.2f}%{RESET} {DIM}({format_num(ctx_tokens)} / {format_num(max_tokens)}){RESET}"
    right2 = f"{BOLD}LIVRE:  {RESET}  {WHITE}{format_num(rem_tokens)}{RESET}{alert_txt}"

    left3 = f"{BOLD}LIM 5H:{RESET}  {fh_color}{fh_bar}{RESET} {fh_color}{fh_pct:5.1f}%{RESET} {DIM}(reseta em {fh_reset}){RESET}"
    right3 = f"{BOLD}SEMANAL:{RESET}  {wk_color}{wk_bar}{RESET} {wk_color}{wk_pct:5.1f}%{RESET} {DIM}(reseta em {wk_reset}){RESET}"

    left4 = f"{BOLD}TURNO: {RESET}  {WHITE}#{turns_count}{RESET} {DIM}│{RESET} In: {BLUE}{format_num(in_tokens)}{RESET} Out: {MAGENTA}{format_num(out_tokens)}{RESET} {DIM}│{RESET} {GREEN}{cost_str}{RESET}"
    right4 = f"{BOLD}GRAFO:  {RESET}  {CYAN}{graph_info}{RESET}"

    line1 = f"  {pad_to(left1, LEFT_WIDTH)}{SEP}{right1}"
    line2 = f"  {pad_to(left2, LEFT_WIDTH)}{SEP}{right2}"
    line3 = f"  {pad_to(left3, LEFT_WIDTH)}{SEP}{right3}"
    line4 = f"  {pad_to(left4, LEFT_WIDTH)}{SEP}{right4}"

    now_hm = datetime.datetime.now().strftime("%H:%M")
    header_title = f" [ {CYAN}STATUS LINE PRO{RESET} {DIM}──{RESET} {WHITE}ORCA ADE{RESET} {DIM}──{RESET} {DIM}{now_hm}{RESET} ] "
    ht_len = visible_width(header_title)
    TOTAL_WIDTH = 96
    fill_right = max(0, TOTAL_WIDTH - 4 - ht_len)
    top_bar = f"{DIM}──{RESET}{header_title}{DIM}{'─' * fill_right}{RESET}"
    bottom_bar = f"{DIM}{'─' * TOTAL_WIDTH}{RESET}"

    sys.stdout.write(f"{top_bar}\n{line1}\n{line2}\n{line3}\n{line4}\n{bottom_bar}\n")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
