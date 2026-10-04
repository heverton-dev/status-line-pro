#!/usr/bin/env python3
"""statusline_renderer.py
Painel enriquecido mantendo o grid simetrico 3x3 de alta densidade sem poluir nem aumentar a altura:
- Linha 1: MODELO + Projeto raiz │ BRANCH + Git dirtiness (+mods, +untracked)
- Linha 2: JANELA (barra alta fidelidade, %, tokens) │ LIVRE + Alerta de compactacao
- Linha 3: TURNO (In, Out, Cache) │ CUSTO + Duracao / Velocidade estimada
"""
import json
import os
import re
import subprocess
import sys
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
        # Pega só o nome da branch limpo
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

    # Cores ANSI
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

    # Latência/Duração se presente
    duration = data.get("duration_ms") or data.get("latency_ms")
    dur_str = ""
    if duration and duration > 0:
        dur_str = f" {DIM}│{RESET} {format_num(duration / 1000.0)}s"

    # 3 Itens Esquerda (56 colunas)
    left1 = f"{BOLD}MODELO:{RESET}  {CYAN}{model}{RESET} {DIM}({project_name}){RESET}"
    left2 = f"{BOLD}JANELA:{RESET}  {color}{bar_str}{RESET} {color}{pct:5.2f}%{RESET} {DIM}({format_num(ctx_tokens)} / {format_num(max_tokens)}){RESET}"
    left3 = f"{BOLD}TURNO: {RESET}  In: {BLUE}{format_num(in_tokens)}{RESET}  Out: {MAGENTA}{format_num(out_tokens)}{RESET}  Cache: {CYAN}{format_num(cache_tokens)}{RESET}"

    # 3 Itens Direita
    right1 = f"{BOLD}GIT:{RESET}    {CYAN}{git_info}{RESET}"
    right2 = f"{BOLD}LIVRE:{RESET}  {WHITE}{format_num(rem_tokens)}{RESET}{alert_txt}"
    right3 = f"{BOLD}CUSTO:{RESET}  {GREEN}{cost_str}{RESET}{dur_str}"

    LEFT_WIDTH = 56
    SEP = f" {DIM}│{RESET}   "

    line1 = f"  {pad_to(left1, LEFT_WIDTH)}{SEP}{right1}"
    line2 = f"  {pad_to(left2, LEFT_WIDTH)}{SEP}{right2}"
    line3 = f"  {pad_to(left3, LEFT_WIDTH)}{SEP}{right3}"

    div = f"{DIM}────────────────────────────────────────────────────────────────────────────────────────────────{RESET}"

    sys.stdout.write(f"{div}\n{line1}\n{line2}\n{line3}\n{div}\n")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
