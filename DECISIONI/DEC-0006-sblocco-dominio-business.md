# DEC-0006 — Sblocco del dominio business: i 13 specialisti diventano assegnabili

```yaml
id: DEC-0006
stato: approvato
livello: 2
data: 2026-10-08
approver: LB-MASTER ORCHESTRATOR (il Lead della sessione), su mandato del CEO
supera:
```

## Problema

Il dominio business era **dichiarato ma inoperabile**. I 13 specialisti erano elencati in una tabella Markdown con quattro colonne in prosa; nessuna riportava `capabilities`, `authorized_task_types` o `excluded_task_types`.

Conseguenze verificate:

1. `python3 tools/cards.py check` marcava **13 card su 40 come non assegnabili**.
2. `python3 tools/cards.py match strategy`, `pricing_analysis`, `icp`, `unit_economics`, `growth_experiment` → `nessun match … STOP`, uscita 1. Nessun task di business poteva essere assegnato a nessuno.
3. Il documento stesso si contraddiceva: `AGENT-CARDS-BUSINESS.md:3` promette «Tutte sono `inactive` finché BUSINESS ORCHESTRATOR non assegna un contract business **con match esplicito**», ma senza task type il match non può esistere.
4. **Gli owner dei gate business erano irraggiungibili**: Strategy → `lb-business-coach`, Brand → `lb-brand-identity` / `lb-archetypal-branding`, Legal → `lb-legal`, Finance → `lb-finance`. Un artefatto business non avrebbe potuto passare i propri gate, e `QUALITY-GATES.md` prevede lo STOP quando l'indipendenza non è possibile.

Effetto sul modello aziendale: la metà «**cosa, perché e per chi**» non era eseguibile da nessun agente. Il codice si fermava correttamente davanti a un catalogo incompleto: non era un difetto del runtime, era un difetto del catalogo.

## Opzioni

1. **Normalizzare la tabella in card YAML**, derivando i campi dalle missioni e dalle esclusioni già scritte nel documento.
2. **Scrivere un catalogo business nuovo** — inventerebbe competenze non dichiarate.
3. **Lasciare il catalogo com'è e usare Transient Worker** per ogni task business — funziona, ma richiede autorizzazione e Decision Record ogni volta, e lascia 13 card inutilizzabili a registro.
4. **Non fare nulla** — metà azienda resta inerte.

## Evidenze

- `cards.py check` prima dell'intervento: `13` card non assegnabili, `campi assenti: ['capabilities', 'authorized_task_types', 'excluded_task_types']`.
- `cards.py match` su sette task type di business: tutti `nessun match`, uscita 1.
- Le missioni erano **già dichiarate**: «strategia, OKR, portfolio analysis», «pricing analysis», «ICP, personas, segmentazione, ricerca utenti», «budget, unit economics, cash-flow scenario, business case» e così via. Mancava la forma, non il contenuto.
- Le esclusioni erano **già dichiarate**: «spesa, pubblicazione, delivery tecnico», «sconti, firma, invio offerta», «pagamenti, fiscal advice, firma».
- `QUALITY-GATES.md` nomina gli owner business dei gate: tutte card non assegnabili.
- Audit indipendente (2026-10-08) ha classificato questo come **blocking** per l'obiettivo «ogni progetto è una startup».

## Scelta

**Opzione 1 — normalizzazione, non invenzione.**

Ogni riga della tabella diventa una card YAML completa. La regola di derivazione è meccanica e verificabile:

| Campo | Da dove viene |
|---|---|
| `capabilities` | la missione dichiarata, in forma di identificatori |
| `authorized_task_types` | la stessa missione: sono i task che la card già diceva di poter fare |
| `excluded_task_types` | la colonna «Esclusioni essenziali», già scritta |
| `mission` | la colonna «Missione primaria e task autorizzati», testo invariato |
| `formation.models` | la colonna «Modelli di riferimento iniziali», invariata |
| `permissions`, `autonomy`, `escalation`, `tools`, `accessible_memory`, `definition_of_done` | ereditati dal blocco comune, **invariati** |

**Nessun permesso nuovo, nessuna autonomia nuova.** Le card restano `permissions: {repository: none, production: none, external_send: none, payments: none}`, `autonomy: {analyse: automatic, commit: forbidden}`, con escalation all'orchestratore business. Ciò che cambia è solo che ora il match è calcolabile.

Il parser `ad_registry.parse_business` legge i blocchi YAML e mantiene la lettura della tabella come fallback, per i cataloghi non ancora normalizzati.

## Conseguenze

- **40 card su 40 assegnabili.** `cards.py check` riporta **0 problemi bloccanti** e 27 note di completezza (il campo `mission` sulle card tecniche, drift noto e non bloccante).
- **43 task type di business** ora risolvibili; i due domini non ne condividono nessuno, quindi un task business non può finire su una card tecnica e viceversa.
- **I quattro gate business** (Strategy, Brand, Legal, Finance) hanno owner assegnabili: un artefatto business può essere prodotto e validato.
- Un documento normativo di root è cambiato (`AGENT-CARDS-BUSINESS.md`): snapshot di integrità rigenerato.
- I test asserivano il contrario e sono stati riscritti: ora verificano che **ogni** specialista sia assegnabile, dichiari i campi critici, escluda almeno un task type, e che nessun task type sia condiviso fra i domini.
- La fixture `contract_business_unassignable.yaml` è stata sostituita da `contract_business_no_match.yaml`: il caso «card non assegnabile» non esiste più nel catalogo reale, quindi si copre con una card sintetica privata del match, e si testa il caso reale che resta — un task business assegnato alla card sbagliata.
- `cards.py check` distingue ora **problemi bloccanti** (card non assegnabili, drift fra documenti) da **note di completezza** (campi non dichiarati che non impediscono l'assegnazione).
- `ad-agent-cards` e `ad-kickoff` sono allineati: non parlano più di una lacuna che non esiste.
- **Limite dichiarato**: i task type sono derivati dalla prosa. Sono fedeli alla missione scritta, ma restano una trascrizione: se una card deve poter fare qualcosa che la sua missione non dice, serve una modifica esplicita alla card, non un'allusione.

## Metrica

Task type di business risolvibili da `cards.py match` (atteso: 43) e gate business con owner assegnabile (atteso: 4 su 4). Si misura nella revisione dei 30 giorni insieme al tasso di contract business che superano la validazione.

## Data di revisione

2026-11-07
