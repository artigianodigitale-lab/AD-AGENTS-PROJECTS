# Rilascio 1.8.0 — AD-AGENTS-PROJECTS

**Data:** 2026-11-17 · **Commit di rilascio:** `bf42cbe` · **Tag:** `v1.8.0`
**Stato dei debiti:** 0 aperti (48 chiusi con prova + 8 accettati con `DEC-0125`)

## Cosa contiene

AD-AGENTS-PROJECTS è un **motore di governance** per agenti AI: dà regole, permessi,
consenso, prove e memoria, e dove può **blocca**. Non è un prompt più lungo: è un sistema
che si installa.

### Le tappe (M0–M10), tutte chiuse

| Tappa | Cosa ha lasciato | Prova |
|---|---|---|
| M0/M1 | macchina pulita, 18 progetti in `Progetti/`, registri per progetto con collegamenti, vista operativa e Blueprint generati | `ci.py` verde |
| M2 | sicurezza misurabile: `SECURITY.md` (OWASP 2026), 12 controlli, sandbox bubblewrap, 15 tool MCP pinnati | `test_sicurezza` |
| M3 | crawler: robots, dedup, rate limit, guardia SSRF (anche redirect), provenienza, browser headless; `CRAWLING.md` | 1.000 pagine locali, 0 duplicati |
| M3b | Code Mode sul MCP: 2 tool invece di 13, script in sandbox, −79,6% definizioni | `test_codice` |
| M4 | memoria lessicale con provenienza (`file:riga`+sha256) e cache verificabile fuori dal repository | eval 9/9, `test_memoria`, `test_cache` |
| M5 | build incrementale (89,6 s → 0,07 s a caldo) e cache del crawler | `tools/build.py` |
| M6 | flight recorder: primo colpo 68,7%, lezioni→controlli 55,7%, terza domanda 100%, 0,42 errori/task | `tools/traiettorie.py` + baseline |
| M7 | tela business verificabile: 11 sezioni, fonte e data su ogni cifra | `test_business` 20 controlli |
| M8 | sei guardie: contract mosso rifiutato, verbali immutabili, cartelle nuove non numerate bloccate, troncamento dichiarato, lista prodotti derivata, MODEL-ROUTING allineato | 4 test, 28 controlli |
| M9 | sigillo stabile nel tempo, Blueprint a tre stati, tela delle tappe, prodotti derivati | 4 test, 24 controlli |
| M10 | prodotti/registri: falsy nel brief, autodetect, cancellazioni del gancio, tappe chiuse con permessi, orari nei progetti, vincoli contro criteri, test autosufficiente, regola UTC | 2 test, 25 controlli |

### Cosa sa fare AAP, in pratica

- **Governare un lavoro**: richiesta → milestone approvata → contract con permesso →
  sprint → evidenze → gate indipendente → rapporto; niente parte senza consenso.
- **Bloccare**: scritture fuori dai permessi, contratti cambiati a gate aperto, verbali
  riscritti, export senza evidenze.
- **Ricordare**: memoria con provenienza, cache con TTL, registri (errori, drift, decisioni).
- **Misurare**: suite deterministica, prove comportamentali con baseline, flight recorder.
- **Leggere il web** con regole: robots, rate limit, SSRF, provenienza.
- **Fare analisi business** con una tela controllabile (fonti e assunzioni dichiarate).
- **Risparmiare contesto**: Code Mode, build incrementale, cache.

### Come si usa (in breve)

```sh
python3 tools/accendi.py                     # verifica che l'engine sia acceso
python3 tools/setup.py --check               # cosa manca, senza scrivere
python3 tools/setup.py                       # monta il cancello sui profili DSH
python3 tools/init.py --nome "..." --ceo "..."   # solo su una copia nuova
```

Procedura completa in `AGENTS.md`; catalogo comandi in `tools/README.md`; descrizione
pubblica in `README.md`.

## Verifica del rilascio

La verifica si fa in **due profili**, e tutti e due sono dichiarati.

### Profilo 1 — macchina completa (dove il motore vive)

| Controllo | Esito |
|---|---|
| `python3 tests/ci.py` | **VERDE 72** |
| `python3 tests/ci.py --full` | **VERDE 82/0** |
| `python3 tools/tests/test_ad_org.py` | **PASS 482** |
| `python3 tools/coherence.py` | OK, 44 comandi |
| `python3 tools/stato.py check` | AGGIORNATO |
| `python3 tools/verbali.py check` / `errori.py check` | OK |
| `git status --porcelain` | vuoto |

### Profilo 2 — copia nuda del bundle (solo repository)

Clonata da `backup/ad-agents-projects-1.8.0.bundle` in `/tmp`:

- tag `v1.8.0` presente, `VERSION` 1.8.0, `git fsck` senza errori, albero pulito: **OK**;
- `tests/ci.py --fast` sulla copia: **8 controlli rossi dichiarati** (`coerenza`, `errori`,
  `test-mcp`, `test-100-aap`, `test-arti`, `test-sandbox`, `test-sicurezza`, `test-codice`).

Perché: quei controlli leggono la **macchina** — i 18 progetti in `Progetti/` (fuori dal
repository, `DEC-0082`), il profilo DSH in `~/.dsh`, i collegamenti dei registri. In una copia
nuda non trovano nulla: sono rossi **per costruzione**, non per un difetto del codice. È
`DRIFT-039`, `ACCEPTED` con `DEC-0126`. Chi riceve il solo repository sappia questo: la suite
piena la pretende la macchina.

## Limiti dichiarati (non nascosti)

- L'enforcement è un'**euristica** sulla shell; il confine affidabile è il `write_scope`.
- Il retrieval della memoria è **lessicale** (i sinonimi possono sfuggire).
- M6 misura il **processo**, M7 la **struttura** di un'analisi: nessuno dei due promette che
  la strategia sia giusta.
- La sandbox non incapsula DSH; in Code Mode `~/.dsh` è nascosto.
- **Nessun remote git**: il backup è locale (`git bundle`). Debito dichiarato in `AGENTS.md`.
- **La suite non è autosufficiente** in una copia nuda (`DRIFT-039`, `DEC-0126`): i controlli
  che leggono la macchina sono dichiarati sopra.


## Backup e ripristino

```sh
git bundle create backup/ad-agents-projects-1.8.0.bundle --all
git bundle verify backup/ad-agents-projects-1.8.0.bundle
git clone ad-agents-projects-1.8.0.bundle <cartella>   # ripristino
```

Il file `.bundle` è in `backup/`, che git ignora: non entra nel repository.

## Azioni irreversibili

Il rilascio **non** pubblica niente: non c'è remote, non c'è invio esterno. Tag e bundle
sono locali. La pubblicazione resta una decisione del CEO con la sua destinazione.
