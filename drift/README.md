# drift — divergenze fra documenti e realta'

Una voce per ogni divergenza **trovata e non ancora sanata**. Il registro serve a non dover scegliere fra ignorare una discrepanza e aprire un Decision Record — che per una nota sarebbe sproporzionato.

**La regola che lo governa: si registra, non si corregge in silenzio.** La correzione richiede un Decision Record; la registrazione no. Chi trova una divergenza la scrive qui e la porta al CEO, invece di "sistemare" documenti mentre fa altro.

## Legenda

| Campo | Ammessi | Note |
|---|---|---|
| `Severita'` | `CRITICAL` `HIGH` `MEDIUM` `LOW` `INFORMATIONAL` | `CRITICAL` = perdita di dati, sicurezza aperta, o regola aggirabile |
| `Stato` | `OPEN` `FIXED` `CLOSED` `ACCEPTED` | `ACCEPTED` = divergenza nota e deliberata, non un difetto |
| `Chiuso` | data ISO | obbligatorio se lo stato e' `FIXED` o `CLOSED` |
| `Decisione` | `DEC-nnnn` | obbligatorio se lo stato e' `FIXED` o `CLOSED`, e deve esistere in `DECISIONI/` |

Una chiusura senza Decision Record non e' una chiusura: e' una modifica silenziosa con un'etichetta.

## Perche' esiste, con gli occhi aperti

Anche il Continuity Pack di `3. AD-Marketing-Factory` — che e' un corpus serio — ha il proprio registro drift **gia' invecchiato**: `DRIFT-102` documenta che `middleware.ts` e' citato da 18 documenti ed e' stato migrato a `proxy.ts` con Next 16, e non e' stato corretto. Un registro che nessuno legge diventa un'illusione di controllo.

Quindi: **questo registro ha bisogno di un lettore.** Va riletto nella revisione dei 30 giorni e nella review strategia del primo lunedi' del mese, insieme a `ad-evolution`. Se non viene riletto, va cancellato: un registro morto e' peggio di nessun registro.

## Controllo deterministico

```sh
python3 tools/drift.py check      # le voci sono complete e coerenti?
python3 tools/drift.py list
```

`check` esce 1 se un ID non e' contiguo, se manca un campo obbligatorio, se un valore non e' ammesso, o se una chiusura non cita un Decision Record esistente.

---


> **Alcune voci non ci sono piu', e i loro numeri nemmeno si riusano.**
> Questa e' la versione che si distribuisce: le divergenze che riguardavano i
> progetti della macchina da cui e' stata ricavata sono rimaste **li'**, dove sono
> successe. Gli id tolti (DRIFT-001, DRIFT-003, DRIFT-004, DRIFT-012, DRIFT-016, DRIFT-017) **non si riassegnano**:
> un identificatore non si riusa, come non si sceglie.

## DRIFT-002 — Il campo `product` elenca 3 prodotti, le cartelle numerate sono 17

| Campo | Valore |
|---|---|
| **Severita'** | MEDIUM |
| **Documento dice** | `contratti/_TEMPLATE.yaml:16` — `product: artigiano-digitale | ad-stock-tracker | biocimatica | altro` |
| **Realta' dice** | 17 cartelle prodotto nella root, con nomi che non corrispondono a quell'elenco |
| **Rischio** | il campo e' inutilizzabile per l'analisi per prodotto: quasi tutto finisce in `altro`, e il valore informativo e' zero |
| **Stato** | OPEN |
| **Evidenza** | `ls -d [0-9]*/` → 17; `contratti/_TEMPLATE.yaml:16` |

## DRIFT-005 — I contatori del pack sono superati

| Campo | Valore |
|---|---|
| **Severita'** | LOW |
| **Documento dice** | Continuity Index §0 — «Prisma models **33**», «API `route.ts` **69**», «UI `page.tsx` **43**», tutte `VERIFIED` |
| **Realta' dice** | 34 modelli, 72 route, 43 pagine. I modelli e le route sono cresciuti; le pagine coincidono |
| **Rischio** | una metrica etichettata `VERIFIED` che non lo e' piu' mina la fiducia in tutte le altre |
| **Stato** | OPEN |
| **Evidenza** | `grep -c '^model ' prisma/schema.prisma` → 34; `find app/api -name route.ts` → 72 |

## DRIFT-006 — `.brain/` non era protetto dall'enforcement

| Campo | Valore |
|---|---|
| **Severita'** | CRITICAL |
| **Documento dice** | la costituzione dichiarava protette le «cartelle prodotto»: i percorsi che iniziano con un numero |
| **Realta' dice** | `.brain/` e `tools/` rispondevano «fuori dalle cartelle prodotto», quindi liberamente scrivibili senza contract. Ma `.brain/` e' symlinkato in `~/.dsh/AGENTS.md` e `~/.agents/skills/`, e `tools/` e' l'autorita' che il plugin interroga: un agente poteva riscrivere l'enforcement che lo blocca, o `settings.json` per eseguire codice arbitrario nel processo host |
| **Rischio** | escalation di privilegi, esecuzione arbitraria, e ogni altra regola aggirabile da chi controlla la macchina che le impone |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-08 |
| **Decisione** | DEC-0009 |
| **Evidenza** | `tools/ad_scope.py` — `GOVERNANCE_PATHS`; `tools/tests/test_ad_org.py` |

## DRIFT-007 — `camoufox-env/` rende rosso il gate del progetto, e solo in locale

| Campo | Valore |
|---|---|
| **Severita'** | HIGH |
| **Documento dice** | `eslint.config.mjs` dichiara di escludere cio' che non e' codice del progetto — `.next`, `out`, `build`, `.open-next`, `.wrangler`, `node_modules` — con la nota AMF-38: *«Il preview di wrangler lascia un bundle `worker.js` da 17 MB dentro `.wrangler/tmp`: ESLint lo lintava e andava in OOM»* |
| **Realta' dice** | `camoufox-env/` e' un virtualenv Python **giitignorato** con **318 file JS** su 5.607 file totali, e **non e' negli ignore**. Effetti: `eslint .` produce **2343 errori** (lint exit 1), e Turbopack va in panic su `symlink camoufox-env/bin/python is invalid, it points out of the filesystem root` (build exit 1). In CI il venv non esiste, quindi **lo stesso comando passa in CI e fallisce in locale** |
| **Rischio** | il gate di verifica del progetto e' inutilizzabile sulla macchina di chi ci lavora. Ogni modifica viene validata solo dalla CI, cioe' dopo il push: nessuno puo' verificare prima di consegnare, e l'errore impiega un ciclo intero a emergere |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-08 |
| **Decisione** | DEC-0014 |
| **Nota di chiusura** | `camoufox-env/**` aggiunto agli ignore di ESLint, e il virtualenv spostato fuori dal progetto in `~/.cache/mf-camoufox-env` (`CAMOUFOX_VENV` per sovrascriverlo). Verificato: `lint` exit 0, `build` exit 0 |
| **Evidenza** | `find camoufox-env -name "*.js" \| wc -l` → 318; `git check-ignore -v camoufox-env` → `.gitignore:34`; `npm run lint` → exit 1, 16130 problemi; `next build` → `TurbopackInternalError`. Misurato il 2026-10-08 |

## DRIFT-008 — Il bootstrap del database di test fallisce su un database nuovo

| Campo | Valore |
|---|---|
| **Severita'** | MEDIUM |
| **Documento dice** | `scripts/run-all-smokes.ts` «Costruzione del database di test dallo schema Prisma…», e `.env.example` indica `MFA_TEST_DATABASE_URL="file:/tmp/mfa-test.db"` come il modo corretto di eseguire gli smoke |
| **Realta' dice** | con `MFA_TEST_DATABASE_URL="file:/tmp/...db"` nuovo, `test:all` esce 1: `PrismaClientKnownRequestError P2021 — The table main.Project does not exist in the current database`, su `scripts/seed-test-fixtures.ts:37`. Il runner annuncia la costruzione dello schema e poi semina su un database vuoto |
| **Rischio** | gli smoke non sono eseguibili localmente: la verifica di regressione del progetto e' di fatto solo in CI. La causa **non e' stabilita** — puo' essere l'ordine fra `db push` e seed, oppure una connessione che usa `DATABASE_URL` invece di `MFA_TEST_DATABASE_URL` |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-08 |
| **Decisione** | DEC-0014 |
| **Nota di chiusura** | il runner ora punta `DATABASE_URL` **e** `MFA_TEST_DATABASE_URL` allo stesso database temporaneo, quindi e' ermetico rispetto all'ambiente di chi lo lancia. Verificato con la variabile impostata: `test:all` exit 0, 59 PASS / 0 FAIL |
| **Evidenza** | `/tmp/baseline/testall.log`, esecuzione del 2026-10-08 con Node 24.21.0 |

## DRIFT-009 — I contract del 2026-10-08 non soddisfano l'invariante 13

| Campo | Valore |
|---|---|
| **Severita'** | LOW |
| **Documento dice** | `TASK-CONTRACTS.md` e la costituzione (invariante 13): un contract che scrive in una cartella prodotto dichiara `milestone` e `sprint`, e lo sprint deve essere aperto |
| **Realta' dice** | i cinque contract del 2026-10-08 — `GOV-000`, `SEC-001`, `FIX-001`, `SEC-002`, `REL-001` — non hanno quei campi, perche' precedono la regola. Rieseguiti dal validatore, fallirebbero |
| **Rischio** | nessuno operativo: sono tutti `status: chiuso` e non coprono piu' nulla. Il rischio e' documentale — chi rilegge il corpus trova contract che non rispettano la norma vigente |
| **Stato** | ACCEPTED |
| **Nota di accettazione** | non si riscrivono: la regola e' entrata in vigore dopo, e inventare una milestone retroattiva per farli combaciare sarebbe falso. Restano come record storico del giorno in cui l'invariante 13 non esisteva |
| **Evidenza** | `contratti/*.yaml`; `python3 tools/validate_contract.py contratti/SEC-001.yaml` |

## DRIFT-010 — Per aprire il primo sprint serve un contract, ma il contract pretende lo sprint aperto

| Campo | Valore |
|---|---|
| **Severita'** | MEDIUM |
| **Documento dice** | `TASK-CONTRACTS.md` e la costituzione: la sequenza e' milestone → consenso → sprint → contract. E `ad_contract.validate` emette `sprint-not-open` se il `PROMPT.md` dello sprint non esiste |
| **Realta' dice** | `tools/milestone.py` chiama `ad_scope.evaluate` prima di scrivere (`_guard`), e una scrittura in una cartella prodotto **senza contract attivo e marcatore** viene rifiutata. Sul primo progetto di un ciclo le due regole si bloccano a vicenda: il contract non e' valido senza sprint aperto, e lo sprint non si apre senza contract |
| **Rischio** | il primo sprint di ogni progetto si sblocca solo invertendo l'ordine — contract attivo, poi sprint, poi validazione — cioe' scrivendo per un momento un contract che il validatore respingerebbe. Chi non conosce il passaggio lo interpreta come un divieto e si ferma; chi lo aggira senza dirlo apre una finestra non coperta da nessuna verifica |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-08 |
| **Decisione** | DEC-0024 |
| **Nota di chiusura** | il confine e' **dove si scrive**: finche' il passo dichiarato non e' aperto, il contract copre solo la cartella di quel passo. Il validatore avvisa invece di rifiutare. Quattro asserzioni nuove nella suite |
| **Evidenza** | `tools/ad_milestone.py:193-209` (`_guard`); `tools/ad_scope.py:310-364` (`evaluate`); `python3 tools/validate_contract.py contratti/NLT-001.yaml` prima e dopo l'apertura dello sprint |

## DRIFT-011 — La suite deterministica pretende che nessun contract apra una cartella prodotto

| Campo | Valore |
|---|---|
| **Severita'** | MEDIUM |
| **Documento dice** | `tools/tests/test_ad_org.py:286` — controllo *«nessun contract apre una cartella prodotto»*: nella root reale nessun `write_scope` deve cadere dentro una cartella numerata |
| **Realta' dice** | il sistema milestone introdotto da DEC-0018 prevede che **ogni** lavoro su un progetto sia uno sprint dentro la cartella del progetto: il primo contract di progetto apre quindi per forza una cartella prodotto. Con `NLT-001` (`17. Michele Clementi Project/Milestone 1/`, `.../Studio/`) il controllo fallisce, e la suite si interrompe su quell'asserzione: i gruppi successivi — milestone, evidenze, drift, invariante 13, coerenza, dipendenze — **non vengono piu' eseguiti** |
| **Rischio** | il gate deterministico del sistema e' rosso per costruzione appena un progetto viene aperto, e smette in silenzio di verificare tutto il resto. Chi lo vede rosso impara a ignorarlo: e' il modo in cui un controllo muore |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-08 |
| **Decisione** | DEC-0023 |
| **Nota di chiusura** | il test ora asserisce la regola dell'invariante 13 sui contract **reali** — ogni contract di progetto dichiara milestone e sprint, e lo sprint e' aperto — invece di un fatto sullo stato del workspace. La suite arriva in fondo: 166 controlli |
| **Evidenza** | `python3 tools/tests/test_ad_org.py` esce 1 con `AssertionError: nessun contract apre una cartella prodotto` su `test_scope`; esecuzione morbida degli altri gruppi: **1 fallimento su 107 controlli**. Misurato il 2026-10-08 |

## DRIFT-013 — Un permesso resta attivo dopo che la sua tappa e' chiusa

| Campo | Valore |
|---|---|
| **Severita'** | MEDIUM |
| **Documento dice** | l'invariante 13 lega il lavoro al passo aperto, e il passo si chiude con il suo rapporto. La tappa si chiude quando tutti i passi sono chiusi |
| **Realta' dice** | `NLT-001` e `NLT-002` sono rimasti `active` mentre `Milestone 1` e i suoi due passi erano **chiusi** e i gate superati. Un permesso che resta aperto tiene il progetto **scrivibile per sempre** — e la tappa chiusa dice che non c'e' piu' niente da scrivere |
| **Rischio** | nessuno di sicurezza: i due permessi erano approvati e limitati al progetto. Il rischio e' che «chiuso» e «scrivibile» dicano due cose diverse, e che il prossimo che legge non sappia quale credere |
| **Stato** | OPEN |
| **Nota** | chiusi a mano il 2026-10-08 da `ORD-002` (DEC-0026). **Aggiornamento 2026-10-10**: la cucitura ora ha un controllo — `tools/post-execute` blocca la chiusura di un permesso se la storia del progetto non e' completa (DEC-0028). Resta scoperto il verso opposto: una tappa chiusa con permessi ancora aperti non viene segnalata |
| **Evidenza** | `contratti/17-michele-clementi-project/NLT-00*.yaml`; `17. Michele Clementi Project/Analisi-Prompt-Report/Milestone 1/REPORT.md` |

## DRIFT-014 — Gli orari dichiarati nei record erano inventati, e nessuno li confrontava

| Campo | Valore |
|---|---|
| **Severita'** | HIGH |
| **Documento dice** | ogni record di governo porta la data e l'ora dell'evento: il marcatore dice quando il CEO ha approvato, l'evidenza quando il gate e' stato eseguito |
| **Realta' dice** | il 2026-10-08 **ogni** prova e **ogni** marcatore scritti quel giorno dichiarava un orario **nel futuro** rispetto al momento in cui il file era stato scritto: da 20 minuti (`GOV-000`, dichiarato 14:50, scritto 14:30) a un'ora e mezza (`ORG-001-code-review`, dichiarato 19:05, scritto 17:32) |
| **Rischio** | un registro di governo in cui le date sono inventate non ordina piu' niente: serve a ricostruire **chi ha deciso cosa, e quando**. E l'ordine approvazione -> permesso si basa sugli orari |
| **Causa** | nessuno confrontava le date dichiarate con l'orologio. Erano numeri scritti a mano, e nessun controllo li leggeva |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-08 |
| **Decisione** | DEC-0027 |
| **Nota di chiusura** | le date dichiarate ora corrispondono all'mtime reale dei file; `tools/coherence.py` verifica che nessun record dichiari un orario non ancora arrivato, escludendo `expires` che **deve** essere nel futuro. Trovato dal revisore indipendente di ORD-002, non da me |
| **Evidenza** | `approvazioni/societa/GOV-000.yaml`, `evidenze/ORG-001-code-review.yaml`, `17. Michele Clementi Project/Analisi-Prompt-Report/Evidenze/ORD-002-code-review.yaml` — mtime contro data dichiarata |
| **Trappola scoperta riparando** | riscrivere un file di governo ne cambia l'mtime, e il controllo dell'ordine (approvazione prima del permesso) legge gli mtime: correggere una data **dentro** un record senza rimettere l'mtime **rompe l'ordine** e blocca ogni scrittura coperta dal permesso. Va sempre ripristinato |

## DRIFT-015 — Due firme risultavano date dopo il loro permesso

| Campo | Valore |
|---|---|
| **Severita'** | LOW |
| **Documento dice** | l'ordine e' ricerca -> risposta -> consenso -> permesso. La firma del CEO precede sempre l'autorizzazione a scrivere |
| **Realta' dice** | `SEC-002` e `REL-001` avevano la firma **dopo** il permesso: 17:25 contro 17:18, e 17:55 contro 17:21. L'ordine era invertito |
| **Causa** | due errori sovrapposti, entrambi miei. Primo: gli orari dichiarati erano **inventati** (numeri tondi, piu' tardi della scrittura vera). Secondo: il 2026-10-08, correggendo le date, ho ripristinato l'mtime dei marcatori **proprio su quegli orari inventati** — spostandoli dopo i loro permessi |
| **Chi l'ha trovato** | il controllo dopo-la-scrittura appena aggiunto, in una passata sui 41 record veri. Non un essere umano, non un caso |
| **Rischio** | nessuno di sicurezza: entrambi i permessi sono `chiuso` e non coprono piu' nulla. Il danno e' di verifica — una firma datata dopo il permesso che autorizza e' un record che non dimostra l'ordine che dovrebbe dimostrare. E il modo in cui e' nato dice che **correggere una data puo' rompere l'ordine**: chi rimettera' mano a un record lo sappia |
| **Stato** | FIXED |
| **Chiuso** | 2026-10-10 |
| **Decisione** | DEC-0028 |
| **Nota di chiusura** | orario **ricostruito** a un minuto prima del permesso, e il record lo dichiara nel campo `nota`. L'orario vero non e' recuperabile: e' stato distrutto dal mio ripristino, e inventarne un altro sarebbe stato rifare l'errore che ha causato tutto questo |
| **Evidenza** | `approvazioni/3-ad-marketing-factory/SEC-002.yaml`, `.../REL-001.yaml` |

---

## DRIFT-018 — Cinque permessi sullo stesso percorso: un percorso senza titolare

| Campo | Valore |
|---|---|
| **Severita'** | HIGH |
| **Documento dice** | `GOVERNANCE-AZIENDALE.md` e `TASK-CONTRACTS.md`: un contract autorizza un esecutore su un `write_scope`. E `ERR-0007`/invariante 6: **un contract avvia un solo esecutore** |
| **Realta' dice** | **11 permessi attivi, 5 percorsi con piu' di un titolare.** `tools/` ne ha **cinque** (ADMF-007, ADMF-008, GOV-000, GOV-001, GOV-002); `.brain/` **quattro**; la stessa tappa di Marketing Factory **cinque**. Il cancello lascia passare tutti, **perche' tutti sono validi** |
| **Causa** | Tre, distinte. **(1)** I raggi sono **cartelle**, non file: `tools/` ha 24 file e cinque permessi possono toccarne di diversi. **(2)** **Niente chiude un permesso quando il lavoro finisce**: vive fino alla scadenza, e sette permessi ADMF scadono fra **90 giorni**. **(3)** **Nessuno ha mai guardato**: la sovrapposizione esisteva da giorni e **non c'era uno strumento per vederla** |
| **Chi l'ha trovato** | il CEO, chiedendo *«chi sta lavorando come sessione?»* — e poi la misura, il 2026-10-13 |
| **Rischio** | **Un percorso con due titolari non ha un titolare.** Se qualcosa si rompe nessuno sa di chi era; due scritture sullo stesso file si sovrascrivono senza che nessuno se ne accorga; e un permesso vecchio **rinnova un'autorita' che il lavoro non giustifica piu'** |
| **Stato** | OPEN |
| **Decisione** | DEC-0054 |
| **Evidenza** | `python3 tools/contract_scope.py titolari`, 2026-10-13 |
| **Nota** | La **misura** ora esiste (`titolari`). La **regola** — un percorso, un titolare, e il permesso che finisce col lavoro — e' una decisione del CEO |

---

## DRIFT-019 — Un permesso scaduto resta scritto come attivo

| Campo | Valore |
|---|---|
| **Severita'** | LOW |
| **Documento dice** | il contract dichiara `expires`: e' una locazione, e alla scadenza finisce |
| **Realta' dice** | `ad_scope.py` **applica** la scadenza ✓ — un permesso scaduto non copre piu' niente. Ma il **file** continua a dire `status: active`: `ADMF-011` e' scaduto il 2026-10-12 ed e' ancora scritto come attivo |
| **Causa** | la scadenza e' applicata **a valle** (dal cancello) e non **a monte** (nel registro). Il registro dice una cosa e il cancello un'altra, e chi legge i file vede la prima |
| **Chi l'ha trovato** | io, misurando — e **sbagliando**: il mio primo elenco leggeva i file a mano e contava `ADMF-011` fra gli attivi. Il cancello no |
| **Rischio** | basso: il cancello e' corretto. Ma **due descrizioni della stessa cosa** sono il difetto che questo sistema combatte, e un agente che legge i file crede a quelli |
| **Stato** | OPEN |
| **Decisione** | DEC-0054 |
| **Evidenza** | `ad_scope.py:153` applica `_expired()`; `contratti/societa/ADMF-011.yaml` dice `active` con `expires: 2026-10-12` |

---
