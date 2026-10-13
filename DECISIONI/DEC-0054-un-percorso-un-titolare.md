# DEC-0054 — Un percorso, un titolare

```yaml
id: DEC-0054
stato: approvato
livello: 2
data: "2026-10-13"
approver: CEO
supera: "DEC-0009, DEC-0038 nella parte sui raggi"
```

## Problema

Il CEO ha chiesto *«chi sta lavorando come sessione?»*. Misurando, e' emerso che il problema non era
chi: era **quanti**.

```
11 permessi attivi con un raggio
 5 percorsi con piu' di un titolare

tools/                                    ADMF-007, ADMF-008, GOV-000, GOV-001, GOV-002
.brain/                                   ADMF-008, GOV-000, GOV-001, GOV-002
3. AD-Marketing-Factory/.../Milestone 3/  ADMF-007, ADMF-009, ADMF-010, ADMF-012, ADMF-013
```

Il cancello lascia passare tutti, **perche' tutti sono validi**. E il danno non e' teorico:
**un percorso con due titolari non ha un titolare.** Se qualcosa si rompe nessuno sa di chi era;
due scritture sullo stesso file si sovrascrivono senza che nessuno se ne accorga; e un permesso
vecchio **rinnova un'autorita' che il lavoro non giustifica piu'**.

Tre cause distinte:

1. **I raggi sono cartelle, non file.** `tools/` ha 24 file: cinque permessi sulla stessa cartella
   possono toccarne di diversi, e la sovrapposizione sulla **cartella** non dice niente su quella
   sui **file**
2. **Niente chiude un permesso quando il lavoro finisce.** Vive fino alla scadenza — e sette
   permessi ADMF scadono fra **90 giorni**. I permessi si accumulano come sedimento
3. **Nessuno ha mai guardato**, perche' **non c'era uno strumento per vederlo**: solo leggendo
   venti file a mano

## Opzioni

1. **Non fare nulla** — il cancello continua a lasciar passare tutti. Conseguenza: la
   sovrapposizione cresce a ogni lavoro nuovo, e il giorno che due sessioni toccano lo stesso file
   nessuno sa cosa e' successo. Il costo non e' oggi: e' **la prima volta che due scritture si
   perdono**, ed e' irreversibile.
2. **Un permesso per volta, deciso dal CEO.** Conseguenza: controllo totale. Costo: **ogni**
   lavoro nuovo aspetta, e il CEO diventa il collo di bottiglia di un sistema che esiste per non
   farlo lavorare cosi'. Fonte: e' il difetto opposto a quello che vogliamo.
3. **Un percorso, un titolare — e il permesso finisce col lavoro.** Il cancello **misura** chi
   copre cosa; due permessi sullo stesso percorso sono una **violazione**; un raggio **stretto**
   (i file) e' la norma e una cartella intera l'eccezione. E **chi esegue chiude il proprio
   contract** quando il lavoro e' accettato, perche' **chiudere toglie autorita', non ne da'**.
   Fonte: [Graphify](https://github.com/Graphify-Labs/graphify), che ci ha dato l'idea del
   verdetto che **misura** invece di esentare; e il modello delle **locazioni**, dove un permesso
   scade o si riconsegna, e non resta aperto per inerzia.
4. **Bloccare tutto finche' non e' pulito.** Conseguenza: un registro coerente. Costo: fermare
   il lavoro di due sessioni per una pulizia che nessuna delle due ha causato. **Sproporzionato**,
   e contrario a `DEC-0040`.

## Evidenze

- **La misura**: `python3 tools/contract_scope.py titolari` — 11 permessi, 5 percorsi contesi.
  **Lo strumento e' nuovo**: prima non si poteva vedere
- **`GOV-000` era attivo dal 2026-10-08** e il suo lavoro era finito da giorni: proteggeva
  `tools/` insieme ad altri quattro
- **`ADMF-011` e' scaduto il 2026-10-12** ed e' ancora **scritto** `active`. Ma `ad_scope.py:153`
  **applica** la scadenza: il cancello e' corretto, **il registro dice un'altra cosa** (`DRIFT-019`)
- **Dopo la pulizia dei permessi miei: da 5 percorsi contesi a 3**, e `tools/` da 5 titolari a 3
- **Ho sbagliato due volte misurando anche qui**: il primo elenco leggeva i file a mano invece di
  usare `load_write_scopes()`, e contava un permesso scaduto fra gli attivi. **Nona volta.**

## Scelta

**Opzione 3.** Approvata dal CEO il 2026-10-13 (*«si dobbiamo risolverlo»*).

**Le tre regole:**

1. **Un percorso, un titolare.** Due permessi attivi non possono dichiarare **lo stesso** percorso:
   e' una violazione. Una cartella che ne contiene un'altra e' un **avviso** da guardare — possono
   toccare file diversi
2. **Il permesso finisce col lavoro.** Alla chiusura (passo 12) il contract passa a
   `status: closed`. **Un agente puo' chiudere il proprio contract** — chiudere **toglie**
   autorita' — ma **non** allargarlo, prorogarlo o cambiarne i criteri (invariante 7). Senza
   questa distinzione i permessi si accumulano e solo il CEO puo' pulirli, che e' il collo di
   bottiglia dell'opzione 2
3. **Raggi stretti.** Si dichiarano **i file**. Una cartella intera e' l'eccezione e va giustificata

**E lo strumento che le rende vere:** `python3 tools/contract_scope.py titolari`.

**Applicazione immediata:**
- `GOV-000` **chiuso** — lavoro finito dal 2026-10-08
- `GOV-001` **chiuso** — la parte Cursor e' decaduta con `DEC-0039`; quel che resta va in `GOV-003`
  con **tre percorsi** invece di due cartelle intere

## Conseguenze

- **Da 5 percorsi contesi a 3**, e `tools/` da **5 titolari a 3**. Il resto non e' mio da chiudere:
  i permessi `ADMF-*` sono di un'altra sessione del CEO
- **La misura esiste**: chiunque puo' vedere chi copre cosa, e i conflitti si vedono invece di
  scoprirli
- **Un agente puo' chiudere il proprio permesso**: i permessi smettono di accumulare
- I raggi larghi diventano un'eccezione dichiarata
- Suite e test: da verificare dopo l'adeguamento

## Limiti dichiarati

- **La regola non e' ancora imposta da un controllo.** `titolari` **misura**; niente **rifiuta**
  un contract sovrapposto. La parte «violazione» va scritta in `validate_contract.py`, e
  **non l'ho fatto**: prima la misura, poi la regola, e la regola cambia il comportamento di
  tutte le sessioni
- **`ADMF-011` resta scritto `active` pur essendo scaduto** (`DRIFT-019`). Il cancello e' corretto;
  il registro no. Non l'ho corretto: **non e' mio**
- **I permessi `ADMF-*` restano tre su `tools/`.** Servono tre atti del CEO, non miei
- **Il conflitto sulla tappa di Marketing Factory** (5 titolari sulla stessa cartella) non l'ho
  toccato: sono cinque lavori diversi dello stesso progetto, ed e' la forma in cui il problema
  nasce quando i raggi sono cartelle
- **`titolari` confronta le stringhe dei percorsi**, non i file reali: `tools/` e `tools/x.py`
  sono due stringhe diverse, e il contenimento lo vede solo per prefisso

## Metrica

Percorsi con piu' di un titolare: da **5 a 3**, atteso **zero**. Permessi attivi: da **11 a 10**,
e il numero conta solo se **scende quando il lavoro finisce** — che e' la regola 2.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: quanti percorsi restano contesi, se i permessi si chiudono davvero
alla chiusura, e se qualcuno ha perso una scrittura per una sovrapposizione.>
