# DEC-0011 — Trapianto dei meccanismi del Continuity Pack

```yaml
id: DEC-0011
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Una revisione indipendente del Continuity Pack di `3. AD-Marketing-Factory` ha stabilito cosa di quel corpus vale il trapianto e cosa no. Nella nostra governance mancavano tre cose, e nessuna e' un documento: sono **pratiche verificabili**.

1. **Nessuna etichetta d'evidenza.** `ad_evidence.py` registrava solo `outcome: PASS | FAIL`: dice se un gate e' passato, **non se le affermazioni di chi l'ha prodotto sono provate**. Un'evidenza PASS puo' contenere affermazioni non verificate, e nessuno se ne accorge.
2. **Nessuna dichiarazione dei side-effect.** Il plugin verifica il `write_scope` del contract ma non chiede al produttore cosa ha toccato. Un task che resta nel perimetro con effetti collaterali — un seed sul database, una chiamata esterna — resta invisibile.
3. **Nessuna precedenza fra fonti.** La regola esisteva nel Python (`ad_gates.py` sa che prevale `QUALITY-GATES.md`) e non nel testo normativo. Con due documenti in conflitto, la risoluzione dipendeva da chi leggeva.

## Evidenze

- `ad_evidence.py` dichiarava `VALID_OUTCOMES = ("PASS", "FAIL")`, e nient'altro.
- Il pack documenta il proprio fallimento in `DRIFT-104`: 49 script di smoke ricadevano su `file:./dev.db` e *«una Demo sandbox completa e 9 eventi `auth.login` sono finiti nel DB dell'utente»*. Una dichiarazione dei side-effect li avrebbe resi visibili prima.
- Le definizioni delle etichette esistono in un solo punto del pack (`SPRINT_26_PROJECT_AUDIT_PROMPT.md` §52), con la norma che le rende utili: *«DO NOT HIDE UNCERTAINTY — The audit's value depends more on truthful uncertainty than apparent completeness»*.
- Il pack e' documentario al 100%: nessuno script legge i suoi registri. Il trapianto e' stato scelto **nella forma meccanizzabile**, non in quella documentale.

## Scelta

### C1 — Etichette d'evidenza

Sei valori, chiusi: `VERIFIED` (confermato da codice, config o test attuali) · `DOCUMENTED` (dichiarato, non confermato) · `INFERRED` (dedotto) · `NOT_VERIFIED` (prova insufficiente) · `NOT_AVAILABLE` (la capacita' non esiste) · `DOCUMENTATION_MISMATCH` (documento e realta' si contraddicono).

Il campo `claims:` dell'evidenza associa ogni affermazione portante alla sua etichetta. Un'etichetta fuori elenco **invalida l'evidenza**. Un'affermazione senza etichetta vale `NOT_VERIFIED`, mai `VERIFIED` per default.

`PARTIAL` e `HISTORICAL` **non** sono stati importati: la revisione ha verificato che nel pack non sono definiti da nessuna parte, e che una label fuori elenco (`SUPERSEDED`) e' gia' in uso. Si importa un set chiuso, non un vocabolario in deriva.

### C3 — Dichiarazione obbligatoria dei side-effect

Sei chiavi fisse — `code`, `database`, `schema`, `deps`, `env`, `external_services` — ognuna `YES | NO | NOT_VERIFIED`. Regola: *se non e' verificabile, `NOT_VERIFIED`; mai inventare `NO`*.

Un'evidenza senza dichiarazione, o con una incompleta, o con un valore fuori elenco, **non conta**: il gate risulta `INVALID` e il verdetto `REJECT`. In piu', dichiarare `database: NO` quando il `write_scope` tocca dati persistenti e' una **contraddizione** e viene rifiutato.

### C4 — Precedenza fra fonti

Tabella in `GOVERNANCE-AZIENDALE.md`: il codice vince sul documento tecnico, il documento vince sul contract, il contract sul piano, il piano sulla comunicazione, la comunicazione sul report storico. Una divergenza si **registra**, non si corregge in silenzio.

## Conseguenze

- Il verdetto non dice piu' solo «il gate e' passato»: dice **cosa e' stato dichiarato e con quanta certezza**.
- Il complemento mancante del `write_scope` esiste: chi agisce dichiara cosa ha toccato.
- Un conflitto fra documenti e' decidibile senza chiedere al CEO ogni volta.
- 9 fixture di evidenza aggiornate; la suite passa da 122 a **131 controlli**.
- Un documento normativo di root cambiato (`QUALITY-GATES.md`, `GOVERNANCE-AZIENDALE.md`): snapshot rigenerato.
- **Scoperta collaterale, e vale la pena registrarla**: in YAML 1.1 `NO` e' il booleano `False` (il "problema della Norvegia"). Il primo giro di test e' fallito perche' `code: NO` veniva letto come `FALSE`. Il loader ora riporta i booleani a `YES`/`NO`, e il caso e' coperto da un test: chi scrive `NO` senza virgolette ottiene quello che intende, invece di un errore incomprensibile.
- **Limite dichiarato**: le etichette sono validate nella forma, non nella sostanza. Nessun controllo verifica che un `VERIFIED` sia davvero verificato. La disciplina resta umana, e il valore sta nel fatto che ora e' **scritta e datata**, quindi contestabile.

## Cosa non e' stato importato, e perche'

- I **24 invarianti** e i **33 rischi** come contenuto: parlano di sandbox, pubblicazione social, Turso, Cloudflare. Entita' che a livello di agenzia non esistono.
- Il **PHASE 2 TRACE** (UI→API→service→DB): presuppone un'app monolitica, e su 17 progetti eterogenei sarebbe un rito senza oggetto.
- La forma piena del **registro rischi**: 33 voci con catene di dipendenze sono tarate su un prodotto con 34 modelli e 72 route. Se servira', sara' una versione ridotta con data di riesame obbligatoria.
- La convenzione **`SUPERSEDED`**: da noi lo snapshot di hash e l'obbligo di Decision Record sono piu' forti.

## Metrica

Percentuale di evidenze con dichiarazione completa e etichette valide (atteso: 100%). E numero di `REJECT` per contraddizione su `database` / `external_services`: misura se la dichiarazione sta diventando un'abitudine o un ostacolo.

## Data di revisione

2026-11-07
