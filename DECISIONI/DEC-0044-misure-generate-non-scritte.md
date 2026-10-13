# DEC-0044 — Le misure si generano, non si scrivono

```yaml
id: DEC-0044
stato: approvato
livello: 3
data: 2026-10-11
approver: CEO
supera:
```

## Problema

Il report della verifica del lavoro del 10-11 ottobre ha preso **`FAIL` tre volte** sullo stesso
criterio di accettazione — *«ogni affermazione porta la sua prova (comando eseguito ed esito), non un
rinvio»* — mentre **i suoi fatti venivano confermati due volte da verificatori indipendenti** (64
affermazioni rieseguite, tutte vere).

Le tre bocciature, in ordine: un elenco falso e dieci numeri senza comando; lo stesso elenco non
corretto e sei numeri senza comando; un numero falso, **tre citazioni attribuite a un documento che
non le conteneva**, due conteggi invecchiati.

**La causa non e' negligenza, ed e' la ragione di questa decisione:** i numeri erano **scritti a mano**
in un documento che descrive un **mondo in movimento**. La cartella cambiava mentre si scriveva (le
evidenze dei gate, i report, le viste), e **ogni correzione spostava le righe**, rompendo le citazioni
interne. Il secondo rework ha riparato i difetti elencati **e creato tre citazioni nuove sbagliate per
questa ragione esatta**. Curare il documento non risolve: il difetto e' nel metodo.

## Opzioni

1. **Rapporto breve + allegato generato** — il rapporto (10-15 pagine) dice i fatti e **cita**
   l'allegato; l'allegato e' **prodotto da uno script** che esegue le misure, e ogni riga porta il
   comando, l'esito, il codice di uscita e il momento. I rimandi sono per **file e impronta**, non per
   numero di riga. Costo: uno strumento e la riscrittura breve. Rischio: basso. Fonte: il metodo e'
   confermato da un caso pubblico che descrive **lo stesso problema** — un sito che dichiarava «83
   regole» quando erano 89, risolto con «ogni numero documentato ha una fonte unica o un'esenzione
   dichiarata e revisionata»: [ADR 0007 di alint](https://raw.githubusercontent.com/asamarts/alint/refs/heads/main/docs/adr/0007-release-aware-documentation.md),
   consultato il 2026-10-11 dal gate `Strategy` di `ADMF-005` (verificato: `status: accepted`,
   data 2026-07-03)
2. **Congelare la cartella e scrivere in una passata** — nessuna scrittura durante la stesura, misure
   prese una volta, citazioni per file e impronta. Costo: una finestra di congelamento. Rischio:
   medio — dipende dalla disciplina, e oggi **non e' una regola scritta** (e' `ERR-0028`, aperto).
   Fonte: `errori/ERR-0028-prodotto-modificato-durante-il-gate.yaml`, letto il 2026-10-11
3. **Quarto tentativo chirurgico sullo stesso documento** — i dieci difetti sono elencati con la
   prova e un rework puntuale li chiuderebbe. Costo: basso per difetto. Rischio: **alto** — e'
   esattamente cio' che e' stato fatto due volte, e ogni volta ha prodotto difetti nuovi. Fonte:
   `Evidenze/ADMF-002-code-review.yaml` e `ADMF-002-qa.yaml`, che documentano i difetti dei due giri
4. **Non fare nulla** — il report resta com'e': fatti verificati due volte, forma non accettata, con i
   difetti dichiarati. La decisione del CEO sulla regolarizzazione dei documenti **si puo' prendere lo
   stesso**, perche' i fatti sono confermati. Costo: zero oggi. Costo differito: il progetto ha un
   report che nessun gate ha accettato, e la prossima verifica riparte da zero — che e' il lavoro che
   quel report doveva evitare. E' l'opzione di riferimento.

## Evidenze

- `Evidenze/ADMF-001-code-review.yaml` e `ADMF-001-qa.yaml` — i `FAIL` del primo e secondo tentativo
- `Evidenze/ADMF-002-code-review.yaml` e `ADMF-002-qa.yaml` — il terzo `FAIL`, coi difetti elencati
- `piani/2026-10-11-documento-che-invecchia.md` — la proposta, con il costo di ogni opzione
- `3. AD-Marketing-Factory/Analisi-Prompt-Report/Milestone 3/Sprint 2/REPORT.md` — il report bocciato,
  1.593 righe, impronta `f580bee8…`, congelato per tutta la verifica
- La ricerca `ADMF-005` (§ della domanda 6) ha cercato **davvero** se al mondo si fa diversamente:
  ha trovato il caso dell'ADR e **nessun** metodo migliore — e lo dichiara
- `python3 tools/tests/test_ad_org.py` → 314 controlli, per la salute della macchina su cui poggia

## Scelta

**Opzione 1: rapporto breve + allegato generato.** Con l'opzione 4 come ponte: i fatti del report
bocciato **sono verificati** e si usano subito per la decisione del CEO; la forma si rifa' con lo
strumento.

## Conseguenze

- Nasce uno strumento (`ADMF-007`) che esegue le misure e genera l'allegato: le misure **si eseguono**,
  non si scrivono.
- Il rapporto breve che ne seguira' **cita per file e impronta**, non per numero di riga: una
  correzione non rompe piu' i rimandi.
- Cambia il modo in cui si producono le prove di **tutti** i lavori, non solo di questo report.
- `ERR-0028` (il congelamento durante la verifica) **resta aperto**: e' una decisione separata, e
  riguarda `QUALITY-GATES.md`, un documento normativo.
- Il report bocciato **non si cancella**: resta come allegato storico e come prova del perche' di
  questa decisione.

## Metrica

Che un rapporto di verifica **passi il gate senza `FAIL` sulla forma**: nessun numero scritto a mano
fuori dall'allegato, e nessuna citazione interna per numero di riga. Misura: le evidenze dei gate di
`ADMF-007` e del rapporto breve che ne seguira' — in particolare che il gate `Code Review` non trovi
un numero senza il comando che lo produce.

## Data di revisione

2026-11-11

## Esito misurato

Da compilare il 2026-11-11: se lo strumento esiste, se il rapporto breve e' passato il gate, e se i
`FAIL` sulla forma sono scesi a zero.
