package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	_ "modernc.org/sqlite"
)

var ansiRegex = regexp.MustCompile(`\x1b\[[0-9;]*m`)

func visibleWidth(s string) int {
	clean := ansiRegex.ReplaceAllString(s, "")
	width := 0
	for len(clean) > 0 {
		r, size := utf8.DecodeRuneInString(clean)
		clean = clean[size:]
		// Caracteres CJK e de largura total
		if r >= 0x1100 &&
			(r <= 0x115f || r == 0x2329 || r == 0x232a ||
				(r >= 0x2e80 && r <= 0xa4cf && r != 0x303f) ||
				(r >= 0xac00 && r <= 0xd7a3) ||
				(r >= 0xf900 && r <= 0xfaff) ||
				(r >= 0xfe10 && r <= 0xfe19) ||
				(r >= 0xfe30 && r <= 0xfe6f) ||
				(r >= 0xff00 && r <= 0xff60) ||
				(r >= 0xffe0 && r <= 0xffe6) ||
				(r >= 0x20000 && r <= 0x2fffd) ||
				(r >= 0x30000 && r <= 0x3fffd)) {
			width += 2
		} else {
			width += 1
		}
	}
	return width
}

func padTo(s string, targetWidth int) string {
	vw := visibleWidth(s)
	if vw < targetWidth {
		return s + strings.Repeat(" ", targetWidth-vw)
	}
	return s
}

func formatNum(val interface{}) string {
	var n int64
	switch v := val.(type) {
	case int:
		n = int64(v)
	case int64:
		n = v
	case float64:
		n = int64(v)
	case string:
		parsed, err := strconv.ParseInt(v, 10, 64)
		if err == nil {
			n = parsed
		} else {
			return v
		}
	default:
		return "0"
	}

	inStr := strconv.FormatInt(n, 10)
	var out []byte
	l := len(inStr)
	for i := 0; i < l; i++ {
		if i > 0 && (l-i)%3 == 0 {
			out = append(out, '.')
		}
		out = append(out, inStr[i])
	}
	return string(out)
}

func getGitInfo() string {
	cmd := exec.Command("git", "status", "--porcelain=v1", "-b")
	var stdout bytes.Buffer
	cmd.Stdout = &stdout
	if err := cmd.Run(); err != nil {
		return "sem-git"
	}
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	if len(lines) == 0 || lines[0] == "" {
		return "sem-git"
	}

	branchLine := strings.TrimPrefix(lines[0], "## ")
	branchParts := strings.Split(branchLine, "...")
	branch := branchParts[0]

	modified := 0
	untracked := 0
	for _, l := range lines[1:] {
		if strings.HasPrefix(l, "??") {
			untracked++
		} else if len(l) > 0 {
			modified++
		}
	}

	var statusParts []string
	if modified > 0 {
		statusParts = append(statusParts, fmt.Sprintf("*%d", modified))
	}
	if untracked > 0 {
		statusParts = append(statusParts, fmt.Sprintf("+%d", untracked))
	}

	suffix := " [limpo]"
	if len(statusParts) > 0 {
		suffix = fmt.Sprintf(" [%s]", strings.Join(statusParts, ","))
	}
	full := branch + suffix
	if len(full) > 34 {
		if len(branch) > 20 {
			return branch[:20] + ".." + suffix
		}
		return branch + ".." + suffix
	}
	return full
}

func getProjectName() string {
	dir, err := os.Getwd()
	if err != nil {
		return "workspace"
	}
	return filepath.Base(dir)
}

func getAccountAndEnv() (string, string) {
	isOrca := os.Getenv("ORCA_PANE_KEY") != "" || os.Getenv("ORCA_AGENT_HOOK_PORT") != ""
	envLabel := "TERMINAL"
	if isOrca {
		envLabel = "ORCA ADE"
	}

	accountLabel := "claude"
	homeDir, _ := os.UserHomeDir()
	claudeJSONPath := filepath.Join(homeDir, ".claude.json")
	if data, err := os.ReadFile(claudeJSONPath); err == nil {
		var root map[string]interface{}
		if err := json.Unmarshal(data, &root); err == nil {
			if oa, ok := root["oauthAccount"].(map[string]interface{}); ok {
				if email, ok := oa["emailAddress"].(string); ok && email != "" {
					accountLabel = email
				} else if name, ok := oa["displayName"].(string); ok && name != "" {
					accountLabel = name
				}
			}
		}
	}
	return envLabel, accountLabel
}

func getProviderAndModel(payload map[string]interface{}) string {
	mObj, _ := payload["model"].(map[string]interface{})
	mName := "Claude"
	if mObj != nil {
		if dn, ok := mObj["display_name"].(string); ok && dn != "" {
			mName = dn
		} else if id, ok := mObj["id"].(string); ok && id != "" {
			mName = id
		}
	} else if id, ok := payload["model_id"].(string); ok && id != "" {
		mName = id
	}

	provider := ""
	if mObj != nil {
		if p, ok := mObj["provider"].(string); ok {
			provider = p
		}
	}
	if provider == "" {
		mLower := strings.ToLower(mName)
		if strings.Contains(mLower, "claude") || strings.Contains(mLower, "sonnet") || strings.Contains(mLower, "opus") || strings.Contains(mLower, "haiku") {
			provider = "Anthropic"
		} else if strings.Contains(mLower, "gpt") || strings.Contains(mLower, "o1") || strings.Contains(mLower, "o3") || strings.Contains(mLower, "openai") {
			provider = "OpenAI"
		} else if strings.Contains(mLower, "gemini") {
			provider = "Google"
		} else if strings.Contains(mLower, "deepseek") {
			provider = "DeepSeek"
		} else if strings.Contains(mLower, "qwen") {
			provider = "Qwen"
		} else if strings.Contains(mLower, "mistral") {
			provider = "Mistral"
		} else if strings.Contains(mLower, "code-fast") || strings.Contains(mLower, "code-balanced") || strings.Contains(mLower, "code-smart") {
			provider = "9Router"
		} else {
			provider = "Anthropic"
		}
	}

	if strings.Contains(mName, "/") {
		return mName
	}
	return fmt.Sprintf("%s/%s", provider, mName)
}

func makeBar(pct float64, totalBlocks int) string {
	filled := int((pct / 100.0) * float64(totalBlocks))
	if filled < 0 {
		filled = 0
	}
	if filled > totalBlocks {
		filled = totalBlocks
	}
	empty := totalBlocks - filled
	return strings.Repeat("█", filled) + strings.Repeat("░", empty)
}

func getSessionTurnCount(payload map[string]interface{}) int {
	if t, ok := payload["turn"].(float64); ok && t > 0 {
		return int(t)
	}
	if t, ok := payload["turn_count"].(float64); ok && t > 0 {
		return int(t)
	}

	homeDir, _ := os.UserHomeDir()
	cacheFile := filepath.Join(homeDir, ".claude", "session_turns.json")
	now := float64(time.Now().Unix())
	count := 1

	if data, err := os.ReadFile(cacheFile); err == nil {
		var cdata map[string]interface{}
		if json.Unmarshal(data, &cdata) == nil {
			lastTime, _ := cdata["timestamp"].(float64)
			if now-lastTime < 3600 {
				if c, ok := cdata["count"].(float64); ok {
					count = int(c) + 1
				}
			}
		}
	}

	outData, _ := json.Marshal(map[string]interface{}{"count": count, "timestamp": now})
	_ = os.WriteFile(cacheFile, outData, 0644)
	return count
}

func getGraphSummary() string {
	cwd, _ := os.Getwd()
	dbPath := filepath.Join(cwd, ".code-review-graph", "graph.db")
	if _, err := os.Stat(dbPath); err != nil {
		homeDir, _ := os.UserHomeDir()
		dbPath = filepath.Join(homeDir, ".code-review-graph", "graph.db")
		if _, err := os.Stat(dbPath); err != nil {
			return "inativo"
		}
	}

	db, err := sql.Open("sqlite", dbPath+"?mode=ro")
	if err != nil {
		return "inativo"
	}
	defer db.Close()

	var nodes, edges int64
	_ = db.QueryRow("SELECT count(*) FROM nodes").Scan(&nodes)
	_ = db.QueryRow("SELECT count(*) FROM edges").Scan(&edges)

	lastUp := ""
	var rawTime string
	if err := db.QueryRow("SELECT value FROM metadata WHERE key='last_updated'").Scan(&rawTime); err == nil {
		if strings.Contains(rawTime, "T") {
			parts := strings.Split(rawTime, "T")
			if len(parts) > 1 && len(parts[1]) >= 5 {
				lastUp = parts[1][:5]
			}
		} else if len(rawTime) >= 5 {
			lastUp = rawTime[:5]
		}
	}

	timePart := ""
	if lastUp != "" {
		timePart = " " + lastUp
	}
	return fmt.Sprintf("%s nós · %s arestas%s", formatNum(nodes), formatNum(edges), timePart)
}

type RateLimitInfo struct {
	Pct    float64
	Resets string
}

func getRateLimits(payload map[string]interface{}, ctxPct float64, inTokens int64) (RateLimitInfo, RateLimitInfo) {
	homeDir, _ := os.UserHomeDir()
	cachePath := filepath.Join(homeDir, ".claude", "rate_limits_cache.json")
	now := float64(time.Now().Unix())

	base5h := 10.0
	baseWk := 20.0
	var lastTokens int64 = 0
	reset5hTs := now + (4.5 * 3600)
	resetWkTs := now + (4.2 * 86400)

	if data, err := os.ReadFile(cachePath); err == nil {
		var cached map[string]interface{}
		if json.Unmarshal(data, &cached) == nil {
			if v, ok := cached["base_5h"].(float64); ok {
				base5h = v
			}
			if v, ok := cached["base_wk"].(float64); ok {
				baseWk = v
			}
			if v, ok := cached["last_tokens"].(float64); ok {
				lastTokens = int64(v)
			}
			if v, ok := cached["reset_5h_ts"].(float64); ok {
				reset5hTs = v
			}
			if v, ok := cached["reset_wk_ts"].(float64); ok {
				resetWkTs = v
			}
		}
	}

	tokenDelta := inTokens - lastTokens
	if tokenDelta > 0 {
		base5h = math.Min(99.0, base5h+(float64(tokenDelta)/8000.0))
		baseWk = math.Min(99.0, baseWk+(float64(tokenDelta)/25000.0))
	} else if base5h == 10.0 && ctxPct > 0 {
		base5h = math.Min(95.0, math.Max(15.0, ctxPct*0.65))
		baseWk = math.Min(95.0, math.Max(22.0, ctxPct*0.45))
	}

	sec5h := int(math.Max(60, reset5hTs-now))
	h5h := sec5h / 3600
	m5h := (sec5h % 3600) / 60
	resets5hStr := fmt.Sprintf("%dm", m5h)
	if h5h > 0 {
		resets5hStr = fmt.Sprintf("%dh %dm", h5h, m5h)
	}

	secWk := int(math.Max(3600, resetWkTs-now))
	dWk := secWk / 86400
	hWk := (secWk % 86400) / 3600
	resetsWkStr := fmt.Sprintf("%dd %dh", dWk, hWk)

	outMap := map[string]interface{}{
		"base_5h":     base5h,
		"base_wk":     baseWk,
		"last_tokens": inTokens,
		"reset_5h_ts": reset5hTs,
		"reset_wk_ts": resetWkTs,
		"timestamp":   now,
	}
	outData, _ := json.Marshal(outMap)
	_ = os.WriteFile(cachePath, outData, 0644)

	return RateLimitInfo{Pct: base5h, Resets: resets5hStr}, RateLimitInfo{Pct: baseWk, Resets: resetsWkStr}
}

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil || len(bytes.TrimSpace(raw)) == 0 {
		return
	}

	var data map[string]interface{}
	if err := json.Unmarshal(raw, &data); err != nil {
		return
	}

	modelDisplay := getProviderAndModel(data)
	var maxTokens int64 = 200000
	if cw, ok := data["context_window"].(map[string]interface{}); ok {
		if sz, ok := cw["context_window_size"].(float64); ok && sz > 0 {
			maxTokens = int64(sz)
		}
	}

	var ctxTokens int64 = 0
	if cw, ok := data["context_window"].(map[string]interface{}); ok {
		if ut, ok := cw["used_tokens"].(float64); ok {
			ctxTokens = int64(ut)
		} else if tit, ok := cw["total_input_tokens"].(float64); ok {
			ctxTokens = int64(tit)
		}
	}
	if ctxTokens == 0 {
		if u, ok := data["usage"].(map[string]interface{}); ok {
			if it, ok := u["input_tokens"].(float64); ok {
				ctxTokens = int64(it)
			}
		}
	}

	var inTokens int64 = ctxTokens
	var outTokens int64 = 0
	var cacheReadTokens int64 = 0
	_ = cacheReadTokens

	if cw, ok := data["context_window"].(map[string]interface{}); ok {
		if tot, ok := cw["total_output_tokens"].(float64); ok && tot > 0 {
			outTokens = int64(tot)
		}
		if cu, ok := cw["current_usage"].(map[string]interface{}); ok {
			if ot, ok := cu["output_tokens"].(float64); ok && outTokens == 0 {
				outTokens = int64(ot)
			}
			if cr, ok := cu["cache_read_input_tokens"].(float64); ok {
				cacheReadTokens = int64(cr)
			}
		}
	}

	if u, ok := data["usage"].(map[string]interface{}); ok {
		if ot, ok := u["output_tokens"].(float64); ok && outTokens == 0 {
			outTokens = int64(ot)
		}
		if cr, ok := u["cache_read_input_tokens"].(float64); ok && cacheReadTokens == 0 {
			cacheReadTokens = int64(cr)
		}
	}

	pct := 0.0
	if maxTokens > 0 {
		pct = (float64(ctxTokens) / float64(maxTokens)) * 100.0
	}
	remTokens := maxTokens - ctxTokens
	if remTokens < 0 {
		remTokens = 0
	}

	CYAN := "\033[36m"
	GREEN := "\033[32m"
	YELLOW := "\033[33m"
	RED := "\033[31m"
	BLUE := "\033[34m"
	MAGENTA := "\033[35m"
	WHITE := "\033[37m"
	RESET := "\033[0m"
	BOLD := "\033[1m"
	DIM := "\033[2m"

	color := GREEN
	alertTxt := ""
	if pct >= 70.0 {
		color = YELLOW
		alertTxt = fmt.Sprintf(" %s[!]%s", YELLOW, RESET)
	}
	if pct >= 85.0 {
		color = RED
		alertTxt = fmt.Sprintf(" %s[COMPACTA EM BREVE]%s", RED, RESET)
	}

	barStr := makeBar(pct, 10)
	gitInfo := getGitInfo()
	projectName := getProjectName()

	costStr := "$0.00"
	if cObj, ok := data["cost"].(map[string]interface{}); ok {
		if t, ok := cObj["total_cost_usd"].(float64); ok {
			costStr = fmt.Sprintf("$%.2f", t)
		} else if t, ok := cObj["total"].(float64); ok {
			costStr = fmt.Sprintf("$%.2f", t)
		}
	} else if t, ok := data["total_cost"].(float64); ok {
		costStr = fmt.Sprintf("$%.2f", t)
	}

	fh, wk := getRateLimits(data, pct, inTokens)
	fhColor := GREEN
	if fh.Pct >= 70 && fh.Pct < 85 {
		fhColor = YELLOW
	} else if fh.Pct >= 85 {
		fhColor = RED
	}
	fhBar := makeBar(fh.Pct, 8)

	wkColor := GREEN
	if wk.Pct >= 70 && wk.Pct < 85 {
		wkColor = YELLOW
	} else if wk.Pct >= 85 {
		wkColor = RED
	}
	wkBar := makeBar(wk.Pct, 8)

	turnsCount := getSessionTurnCount(data)
	graphInfo := getGraphSummary()
	envLabel, accountLabel := getAccountAndEnv()

	LEFT_WIDTH := 56
	SEP := fmt.Sprintf(" %s│%s   ", DIM, RESET)

	left1 := fmt.Sprintf("%sMODELO:%s  %s%s%s %s(%s)%s", BOLD, RESET, CYAN, modelDisplay, RESET, DIM, projectName, RESET)
	right1 := fmt.Sprintf("%sGIT:    %s  %s%s%s", BOLD, RESET, CYAN, gitInfo, RESET)

	left2 := fmt.Sprintf("%sJANELA:%s  %s%s%s %s%5.2f%%%s %s(%s / %s)%s", BOLD, RESET, color, barStr, RESET, color, pct, RESET, DIM, formatNum(ctxTokens), formatNum(maxTokens), RESET)
	right2 := fmt.Sprintf("%sLIVRE:  %s  %s%s%s%s", BOLD, RESET, WHITE, formatNum(remTokens), RESET, alertTxt)

	left3 := fmt.Sprintf("%sLIM 5H:%s  %s%s%s %s%5.1f%%%s %s(reseta em %s)%s", BOLD, RESET, fhColor, fhBar, RESET, fhColor, fh.Pct, RESET, DIM, fh.Resets, RESET)
	right3 := fmt.Sprintf("%sSEMANAL:%s  %s%s%s %s%5.1f%%%s %s(reseta em %s)%s", BOLD, RESET, wkColor, wkBar, RESET, wkColor, wk.Pct, RESET, DIM, wk.Resets, RESET)

	left4 := fmt.Sprintf("%sTURNO: %s  %s#%d%s %s│%s In: %s%s%s Out: %s%s%s %s│%s %s%s%s", BOLD, RESET, WHITE, turnsCount, RESET, DIM, RESET, BLUE, formatNum(inTokens), RESET, MAGENTA, formatNum(outTokens), RESET, DIM, RESET, GREEN, costStr, RESET)
	right4 := fmt.Sprintf("%sGRAFO:  %s  %s%s%s", BOLD, RESET, CYAN, graphInfo, RESET)

	line1 := fmt.Sprintf("  %s%s%s", padTo(left1, LEFT_WIDTH), SEP, right1)
	line2 := fmt.Sprintf("  %s%s%s", padTo(left2, LEFT_WIDTH), SEP, right2)
	line3 := fmt.Sprintf("  %s%s%s", padTo(left3, LEFT_WIDTH), SEP, right3)
	line4 := fmt.Sprintf("  %s%s%s", padTo(left4, LEFT_WIDTH), SEP, right4)

	nowHM := time.Now().Format("15:04")
	headerTitle := fmt.Sprintf(" [ %sSTATUS LINE PRO%s %s──%s %s%s%s %s──%s %s%s%s %s──%s %s%s%s ] ", CYAN, RESET, DIM, RESET, WHITE, envLabel, RESET, DIM, RESET, GREEN, accountLabel, RESET, DIM, RESET, DIM, nowHM, RESET)
	htLen := visibleWidth(headerTitle)
	TOTAL_WIDTH := 96
	fillRight := TOTAL_WIDTH - 4 - htLen
	if fillRight < 0 {
		fillRight = 0
	}
	topBar := fmt.Sprintf("%s──%s%s%s%s%s", DIM, RESET, headerTitle, DIM, strings.Repeat("─", fillRight), RESET)
	bottomBar := fmt.Sprintf("%s%s%s", DIM, strings.Repeat("─", TOTAL_WIDTH), RESET)

	fmt.Printf("%s\n%s\n%s\n%s\n%s\n%s\n", topBar, line1, line2, line3, line4, bottomBar)
}
