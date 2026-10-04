# Arquitetura e Fluxo de Telemetria

O **Status Line Pro** conecta a API de statusline em tempo real do Claude Code a um renderizador visual monoespaçado de alta fidelidade.

---

## 1. Ciclo de Vida do Evento

1. **Disparo do Claude Code**:
   A cada turno de prompt, chamada de ferramenta ou compactação de contexto, o CLI do Claude Code executa o comando configurado em `settings.json` sob a chave `statusLine`.
2. **Payload JSON**:
   O Claude Code injeta um objeto JSON detalhado via `STDIN`, contendo:
   - `model`: Identificador e nome amigável do modelo (`code-fast`, `Claude 3.7 Sonnet`, etc.).
   - `context_window`: Tamanho máximo (`context_window_size`), tokens usados (`used_tokens`), tokens de entrada e percentual.
   - `usage`: Tokens do turno atual (`input_tokens`, `output_tokens`, `cache_read_input_tokens`).
   - `cost`: Total financeiro gasto na sessão.
3. **Interceptação Dual (Orca ADE vs Terminal Avulso)**:
   - **No Orca ADE**: `bin/claude-statusline.cmd` salva o payload em arquivo temporário, invoca o `src/statusline_renderer.py` para desenhar no terminal e despacha a requisição HTTP POST para o webhook interno do Orca (`http://127.0.0.1:%ORCA_AGENT_HOOK_PORT%/statusline/claude`).
   - **Fora do Orca**: Quando as variáveis de ambiente do Orca (`ORCA_PANE_KEY`, `ORCA_AGENT_HOOK_PORT`) estão ausentes, o script renderiza o painel visual no terminal e encerra imediatamente com exit code 0.

---

## 2. Princípio de Alinhamento Óptico

Renderizadores tradicionais em Shell/Bash falham no alinhamento quando combinam:
1. Códigos de escape ANSI de cor (`\033[36m`).
2. Blocos Unicode (`█`, `░`).
3. Caracteres CJK ou de largura dupla.

O motor `statusline_renderer.py` resolve isso:
- Expurgando regex ANSI (`\x1b\[[0-9;]*m`) antes de calcular largura.
- Usando `unicodedata.east_asian_width` para determinar se o caractere ocupa 1 ou 2 colunas no emulador de terminal.
- Aplicando preenchimento padronizado (`pad_to`) até exatamente a coluna 56 na seção esquerda, garantindo o divisor `│` reto e contínuo.
