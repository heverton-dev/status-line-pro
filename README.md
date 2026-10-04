# Status Line Pro 🚀

Statusline visual de alta densidade, alta fidelidade e tempo real para **Claude Code CLI** no terminal, totalmente compatível com o **Orca ADE** e terminais Windows/POSIX independentes.

---

## 📸 Preview no Terminal (Layout 4 Linhas)

```text
────────────────────────────────────────────────────────────────────────────────────────────────
  MODELO:  code-fast (ecossistema-aidd)                     │   GIT:     aidd/calibracao-pipe.. [*39]
  JANELA:  ██████░░░░  62.32% (124.645 / 200.000)            │   LIVRE:   75.355
  TURNO:   In: 124.645  Out: 310  Cache: 0                  │   CUSTO:   $0.00
  LIM 5H:  ███░░░░░   42.0% (reseta em 2h 15m)               │   SEMANAL: ██░░░░░░   28.5% (reseta em 4d 10h)
────────────────────────────────────────────────────────────────────────────────────────────────
```

---

## ✨ Recursos

- **Grid 4x2 Perfeitamente Alinhado**: 4 linhas de telemetria rica, divisor central contínuo (`│`) e largura fixa calculada em tempo real.
- **Barra de Progresso Unicode de Alta Definição**: Blocos sólidos `█` e de preenchimento `░` com cores ANSI dinâmicas (Verde `< 70%`, Amarelo `70-84%`, Vermelho `≥ 85%`).
- **Alinhamento Óptico Imune a Códigos ANSI**: Cálculo de largura real descartando sequências de escape ANSI e caracteres de largura dupla via `unicodedata.east_asian_width`.
- **Métricas Completas do Contexto**:
  - **Tokens de Entrada / Saída / Cache**: Valores exatos com separadores de milhar (`.`).
  - **Saldo Livre**: Contagem decrescente exata de tokens restantes na janela.
  - **Alerta de Compactação Dinâmico**: Aviso `[COMPACTA EM BREVE]` quando o uso ultrapassa 85%.
  - **Git Status em Tempo Real**: Nome da branch ativa e contagem de alterações pendentes (`*modificados`, `+não-rastreados`).
  - **Custo Acumulado**: Exibição monetária exata por sessão.
  - **Rate Limits (5 Horas e Semanal)**: Barras exclusivas, percentual consumido e contagem regressiva para renovação da cota.
  - **Workspace / Projeto**: Identificação imediata da pasta raiz em uso.
- **Compatibilidade Dual**: Opera perfeitamente dentro do **Orca ADE** (preservando telemetria interna e webhooks) e em terminais avulsos (PowerShell, Windows Terminal, Git Bash).

---

## 📂 Estrutura do Projeto

```text
status-line-pro/
├── bin/
│   ├── claude-statusline.cmd      # Hook do Orca ADE / Windows Command Wrapper
│   └── statusline.cmd             # Wrapper para terminal avulso fora do Orca
├── src/
│   └── statusline_renderer.py     # Motor principal de renderização e cálculo de largura
├── docs/
│   └── ARQUITETURA.md             # Detalhamento de telemetria e integração
├── install.cmd                    # Instalador automatizado para Windows
├── install.sh                     # Instalador automatizado para Linux/macOS
├── package.json                   # Metadados do projeto
└── README.md                      # Documentação completa
```

---

## 🚀 Instalação Rápida

### Pré-requisitos
- Python 3.8+ instalado e no `PATH`.
- `jq` (opcional, para pipelines adicionais).

### Instalação no Windows
Execute o script instalador na raiz do projeto:

```cmd
install.cmd
```

O instalador irá:
1. Copiar `statusline_renderer.py` e `statusline.cmd` para `%USERPROFILE%\.claude\`.
2. Integrar `claude-statusline.cmd` em `%USERPROFILE%\.orca\agent-hooks\`.
3. Ativar o evento `statusLine` no `%USERPROFILE%\.claude\settings.json`.

---

## 🛠️ Teste Manual

Para validar o renderizador com um payload de teste sem precisar abrir o Claude Code:

```powershell
$json = '{"model":{"display_name":"Claude 3.7 Sonnet"},"context_window":{"context_window_size":200000,"used_tokens":124645},"usage":{"input_tokens":124645,"output_tokens":310,"cache_read_input_tokens":60000},"cost":{"total":0.18},"rate_limits":{"five_hour":{"used_percentage":42.0,"resets_in":"2h 15m"},"weekly":{"used_percentage":28.5,"resets_in":"4d 10h"}}}'
$json | python src/statusline_renderer.py
```

---

## 📄 Licença

MIT License.
