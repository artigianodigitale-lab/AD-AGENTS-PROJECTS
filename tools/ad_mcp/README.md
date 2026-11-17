# Il cancello portabile — server MCP di AD Projects

> ENG-002 (sprint A) · DEC-0057 · ENG-011 (registrazione) · DEC-0065.
> Stato: il server **funziona, e' provato e REGISTRATO** in DSH, Cursor, Codex e
> Gemini su questa macchina; ogni altra macchina si registra da sola con un comando.

## Che cos'e', e perche'

Le regole di AD vivevano nei comandi Python: un agente le usava solo se sapeva
quale comando lanciare, e ogni programma (DSH, Cursor, Claude Code, Codex,
Gemini CLI) le raggiungeva a modo suo — o non le raggiungeva.

Questo server le espone in un modo solo, che tutti i client parlano: **MCP**
(Model Context Protocol) su **stdio**, JSON-RPC 2.0, un messaggio per riga.
Non riscrive nessuna regola: chiama le librerie di `tools/`, che restano
l'autorita'. E' lo stesso principio del plugin DSH, che interroga
`contract_scope.py` invece di duplicare il confine.

Solo libreria standard + PyYAML (dipendenza gia' presente). Un server che
richiede un pacchetto non e' portabile, e la portabilita' e' tutto il motivo per
cui esiste.

## Come si avvia

```sh
python3 tools/ad_mcp/server.py
```

Parla su stdin/stdout. Un client gli manda, una riga per messaggio:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ad_session","arguments":{}}}
```

Metodi: `initialize`, `ping`, `tools/list`, `tools/call`. Un metodo sconosciuto
risponde `-32601` con `data.remediation`.

## I dieci tool

| tool | cosa fa | effetti |
|---|---|---|
| `ad_session` | inventario: contratti attivi, registri, tool | legge |
| `ad_contract_check` | «posso scrivere qui? chi lo autorizza?» | legge |
| `ad_contract_validate` | valida un contract contro il registry delle card | legge |
| `ad_cards_match` | cerca la card autorizzata per un tipo di task (nessuna = STOP) | legge |
| `ad_verdict` | verdetto del Quality Gate, stessa regola di `tools/verdict.py` | legge |
| `ad_evidence_check` | identita', schema e copertura di una prova | legge |
| `ad_unknowns` | registro delle incognite: list/check/new/update/resolve | **scrive** il registro |
| `ad_bundle` | pacchetto sigillato di prove: export/check/import | **scrive** file |
| `ad_tree` | impronta dell'albero: record/check | **scrive** il testimone |
| `ad_registry` | legge un registro: errori, drift, decisioni, piani (riassunto o paginato) | legge |

Ogni tool dichiara il proprio schema JSON (`additionalProperties: false`,
`required`, `enum`, `minimum`/`maximum`, `minItems`) e le annotazioni
`readOnlyHint`/`destructiveHint`. **Lo schema si applica**, non si dichiara:
un argomento estraneo o un tipo sbagliato sono `-32602` con il rimedio.

## Il confine

Il server **non legge e non scrive fuori dalla macchina**: ogni percorso che
arriva da fuori viene risolto e, se esce dalla root, **rifiutato** con la
ragione. E ogni destinazione di scrittura passa da `ad_scope`: il server non
concede piu' di quanto conceda il cancello.

Casi provati: `../`, `/etc`, percorsi assoluti, symlink che escono, byte NUL,
percorsi vuoti o di soli spazi, JSON annidato 30.000 volte, UTF-8 non valido,
richieste senza `method`, `params` non oggetto. Tutti rifiutati con
`{code, message, data.remediation}` — e il server resta vivo.

Due dettagli che il gate di ENG-003 ha chiesto di rendere espliciti. Il primo:
`ad_tree` accetta `paths` **solo con `action=record`**; il controllo usa il
perimetro registrato nel testimone, e passare `paths` a `check` e' un errore
(prima veniva validato e poi ignorato: un client che chiedeva un perimetro ne
riceveva un altro). Il secondo: il byte NUL e' rifiutato anche **dentro** i
`paths`, non solo nei parametri singoli — anche li' e' un `-32602` con la
ragione, non un errore interno.

## Limiti dichiarati (non nascosti)

1. **Registrato su questa macchina (ENG-011), non su tutte.** La ricetta e'
   portatile: ogni macchina esegue `--apply` e si registra da sola. Resta aperta
   la voce nel registro dei comandi (`tools/README.md`, ADMF-008): `DRIFT-026`.
2. **Non e' nel registro dei comandi** (`tools/README.md`): quel file e' di
   ADMF-008. E' la divergenza `DRIFT-026`, e la riga va nel **primo contract che
   avra' quel file libero** (dopo la chiusura di ADMF-008): non in ENG-004, che
   non lo possiede, e non in ENG-005, che e' la registrazione nei client.
3. **Nessuna autenticazione**: e' un processo locale su stdio, pensato per un
   client che lo lancia. Un server esposto in rete sarebbe un'altra cosa.
4. **Un client per processo**: nessuna concorrenza provata.
5. **Non legge fuori dalla macchina**, nemmeno per aiutare: un client che chiede
   un file di `~/` riceve un rifiuto.
6. **Protocollo**: `2025-06-18`, solo `tools` (niente prompts/resources/sampling).
7. **Requisiti**: Python **>= 3.11** per validare il TOML di Codex (`tomllib`);
   sugli interpreti piu' vecchi `--check codex` rifiuta con la ragione. Provato su
   **Linux / Python 3.12**, non su Windows o macOS.
8. **`_guard_write` non ha identita' del chiamante.** Autorizza una destinazione se
   *qualunque* contract attivo la copre: un client che passa da questo server
   scrive dove un esecutore di quel contract potrebbe scrivere. Non e' una
   regola per-task, e' una regola path-level — lo stesso limite che il plugin DSH
   dichiara. Chi vuole di piu' lo aggiunge al server, non alla buona volonta'.

## Registrazione nei cinque client — il generatore verificabile

Il blocco di configurazione non si scrive a mano: `tools/ad_mcp/install.py` lo
**genera e lo valida** per ognuno dei cinque client, con il percorso assoluto
della macchina.

```sh
python3 tools/ad_mcp/install.py --list             # i cinque client, dove vive la config
python3 tools/ad_mcp/install.py --print cursor     # il blocco esatto, da copiare
python3 tools/ad_mcp/install.py --check-all        # verifica tutti i blocchi
```

**La registrazione si puo' fare, ed e' portatile (ENG-011, DEC-0065).**
`install.py --apply` scrive la voce nella configurazione del client scegliendo i percorsi
**di questa macchina**, dopo un backup; `--status` dice se la voce e' aggiornata,
assente, non registrata o **stale** (punta a un'altra macchina); `--rollback`
riporta il file com'era (o allo stato «assente» se il file non c'era).

```sh
python3 tools/ad_mcp/install.py --status auto          # stato su QUESTA macchina
python3 tools/ad_mcp/install.py --apply cursor         # registra (con backup)
python3 tools/ad_mcp/install.py --apply auto           # registra i client rilevati
python3 tools/ad_mcp/install.py --apply dsh --dry-run  # mostra, non scrive
python3 tools/ad_mcp/install.py --rollback cursor      # torna indietro
```

La voce usa `python3` dal PATH: un solo campo dipende dalla macchina (il percorso
del server) e si rigenera. **Il cancello su questo non e' un confine di sicurezza:**
difende dalla dimenticanza; il dolo lo vedono git e il revisore (DEC-0063).

Le forme, per riferimento:

**DSH** — non usa `mcpServers`: il profilo carica i plugin da
`~/.dsh/profiles/<profilo>/cordis.patch.yml`, e il server va dichiarato come
entrata del plugin **`@deepseek-ai/dsh-mcp-client`**:

```yaml
- insert:
    - id: ad-projects-mcp
      name: "@deepseek-ai/dsh-mcp-client"
      config:
        transport: stdio
        serverName: ad-projects
        command: python3
        args: ["/percorso/della/macchina/tools/ad_mcp/server.py"]
```

La forma e' quella letta dal client montato (schema `Config`: `transport: stdio`,
`serverName` con `^[A-Za-z0-9_-]{1,32}$`, `command`, `args`). `install.py --print
dsh` la stampa gia' pronta e `--check dsh` la valida. Il profilo si monta al
prossimo avvio. A scrivere quel file e' `tools/ad_mcp/install.py --apply dsh`
(ENG-011): il file del profilo vive in `~/.dsh/`, fuori dalla macchina, e la
registrazione si rigenera con un comando.

**Cursor** — `.cursor/mcp.json` nel progetto (o `~/.cursor/mcp.json`):

```json
{"mcpServers": {"ad-projects": {
  "command": "python3",
  "args": ["/percorso/della/macchina/tools/ad_mcp/server.py"]
}}}
```

**Claude Code** — `claude mcp add ad-projects -- python3 /percorso/tools/ad_mcp/server.py`
(oppure il blocco `mcpServers` in `~/.claude.json`).

**Codex** — la voce `mcp_servers` della configurazione, con
`command = "python3"` e `args = ["/percorso/tools/ad_mcp/server.py"]`.

**Gemini CLI** — il blocco `mcpServers` in `~/.gemini/settings.json`, stessa forma.

In tutti: percorso **assoluto** alla macchina, nessuna variabile d'ambiente,
nessun argomento. Il server parte e si presenta con `initialize`.

## La procedura di congelamento (ERR-0057)

Un gate che giudica un artefatto che cambia non giudica niente. Regola:

1. **Prima di aprire un gate**, si scrive la revisione con le impronte:
   `evidenze/<task_id>-revisione.yaml` con `sha256` di ogni file sotto verifica
   (vedi `evidenze/ENG-002-revisione.yaml` come esempio).
2. Il revisore **verifica le impronte all'inizio e alla fine**. Se una cambia, si
   ferma e dichiara che il prodotto si e' mosso: non certifica niente.
3. **A gate aperto non si scrive** nel perimetro sotto verifica: si annota e si
   aspetta. Nel quarto gate di ENG-002 le 9 impronte sono rimaste identiche
   all'inizio e alla fine: la procedura ha funzionato.

## Come si prova

```sh
python3 tools/tests/test_ad_mcp.py      # il server, dal processo vero (190 controlli)
python3 tools/tests/test_ad_install.py  # generatore + registrazione portatile (159 controlli)
python3 tools/tests/test_evidenza.py    # la regola del verdetto (99 controlli)
```

Il test di parita' e' il piu' importante: `ad_verdict` deve dare lo **stesso**
esito di `tools/verdict.py`. Se il server riscrivesse la regola, prima o poi
direbbe una cosa diversa dal CLI — due autorita' che divergono sono peggio di una
sola.
