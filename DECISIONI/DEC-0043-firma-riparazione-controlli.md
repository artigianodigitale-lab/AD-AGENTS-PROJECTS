# DEC-0043 — La firma sulla riparazione dei due controlli

```yaml
id: DEC-0043
stato: approvato
livello: 3
data: 2026-10-11
approver: CEO
supera:
```

## Problema

`ADMF-004` — la riparazione di due difetti della macchina di governance — ha ricevuto **`ACCEPT`** su
entrambi i gate richiesti (`Code Review` e `QA`), ma il contract ha `approval.human: true`, e la
regola e' esplicita: **`ACCEPT` non e' il rilascio** (`QUALITY-GATES.md`). Senza la firma del CEO il
contract resta `active`, continua a coprire `tools/`, e la riparazione non e' chiusa.

**Cosa e' stato riparato.** La guardia di ambito — il controllo che impedisce di scrivere in un
progetto senza permesso — esisteva in **un solo strumento su sei**, e `blueprint.py` scriveva dove
nessun contract lo copriva. E il **verdetto** sceglieva l'evidenza di un gate **per data, senza
guardare di chi fosse**: **6 permessi su 7** risultavano falliti pur avendo la loro revisione valida.

**Cosa succede se non si decide.** La riparazione resta aperta e i due controlli restano in vigore
*nonostante* il gate li abbia accettati: si confonde «verificato» con «in attesa».

## Opzioni

1. **Firmare e chiudere** — la riparazione e' verificata da due gate indipendenti, con il metodo
   giusto: le prove **eseguono** il caso, e i verificatori hanno **rimesso il difetto su una copia**
   verificando che le prove **fallissero**. Costo: una firma. Rischio: basso, e circoscritto —
   `ACCEPT` non e' rilascio, non autorizza a pubblicare, e non chiude `ERR-0028`. — fonte:
   `Evidenze/ADMF-004-code-review.yaml` e `ADMF-004-qa.yaml`, entrambe del 2026-10-11, sulla stessa
   impronta dell'albero `tools/` (`4574246974f9…12ad`, identica all'apertura e alla chiusura).
   Il principio che la riparazione ripristina — **un controllo che non sa deve rifiutare, non
   concedere** — e' lo standard di riferimento: [OWASP ASVS 4.1.4, *The principle of deny by
   default exists*](https://owasp-aasvs4.readthedocs.io/en/latest/4.1.4.html), consultato il
   2026-10-11. Prima della riparazione la guardia faceva l'opposto: percorso sconosciuto →
   `allowed=True`
2. **Non firmare adesso** — il contract resta `active` e la riparazione aperta. Costo: la macchina
   resta con un `ACCEPT` che non si traduce in chiusura; i permessi non si liberano. Rischio: basso
   tecnico, ma il registro perde di significato. — fonte:
   `contratti/societa/ADMF-004.yaml`, campo `approval.human`, letto il 2026-10-11
3. **Non fare nulla** — e' l'opzione di riferimento, e coincide con (2): non firmare **e'** non
   decidere. Costo: il contract resta `active`, `tools/` resta coperto, e la riparazione non entra
   nella storia come chiusa. — fonte: `QUALITY-GATES.md`, «ACCEPT non e' il rilascio», letto il
   2026-10-11

## Evidenze

- `3. AD-Marketing-Factory/Analisi-Prompt-Report/Evidenze/ADMF-004-code-review.yaml` — gate
  `Code Review`, esito `PASS`, produttore `review`, 2026-10-11T18:55
- `3. AD-Marketing-Factory/Analisi-Prompt-Report/Evidenze/ADMF-004-qa.yaml` — gate `QA`, esito
  `PASS`, produttore `qa`, 2026-10-11T18:58
- `python3 tools/verdict.py --contract contratti/societa/ADMF-004.yaml --evidence <Evidenze/>` →
  `ACCEPT`, con l'avviso «approvazione umana richiesta dal contract»
- `python3 tools/tests/test_ad_org.py` → **314 controlli**, exit 0 (erano 287 prima della
  riparazione)
- `python3 tools/coherence.py`, `cards.py check`, `drift.py check`, `verbali.py check`,
  `errori.py check`, `blueprint.py check`, `stato.py check` → tutti exit 0
- `errori/ERR-0026-blueprint-senza-guardia.yaml` e
  `errori/ERR-0027-evidenza-scelta-senza-filtro.yaml` — chiusi con la difesa verificata
- `DECISIONI/DEC-0008-milestone-e-sprint.md` — il principio «la guardia sta dentro lo strumento»
- Il primo tentativo della riparazione e' stato **bocciato** dal gate (`FAIL`): la guardia lasciava
  passare qualsiasi percorso fuori dall'albero di autorita', e cinque strumenti scrivevano davvero
  con `--root /tmp/...` — riprodotto dall'orchestratore il 2026-10-11

## Scelta

**Opzione 1: firmare e chiudere.** Il percorso — bocciare, correggere, riprovare, verificare con le
mutazioni — e' esattamente cio' che il gate esiste per fare, e il risultato e' verificabile:
**314 controlli** passano, **7 permessi su 7** danno `ACCEPT` con la propria evidenza, e un gate
**senza** evidenza propria resta un'**assenza dichiarata** invece di un'accusa al permesso sbagliato.
Il rework ha anche trovato una **sesta porta** che il gate non aveva elencato: la riparazione e'
**piu' completa** di quanto il gate avesse chiesto.

## Conseguenze

- `ADMF-004` passa a `status: chiuso`: non copre piu' `tools/`.
- `ERR-0026` e `ERR-0027` restano **chiuse** con la difesa verificata.
- `ERR-0028` **resta aperto**: il divieto di modificare un artefatto mentre il gate lo verifica vive
  in `QUALITY-GATES.md` e **non e' stato scritto**. E' una decisione separata, non una conseguenza.
- Il registro delle autorizzazioni ha ora **cinque** permessi di questa giornata da mettere in
  sicurezza: vedi `piani/2026-10-11-quattro-decisioni-sulla-macchina.md`, decisione 2.
- Nessun effetto su prodotti, prezzi o produzione: la riparazione tocca gli strumenti di governance.

## Metrica

Che i **verdetti smettano di essere falsi**: sui permessi del progetto Marketing Factory, i gate
`INVALID` devono restare **0** (erano 9 prima della riparazione), e i `REJECT` residui devono avere
la ragione giusta — `MISSING` per un'evidenza che manca, `FAIL` per un'esecuzione fallita — mai
`INVALID` per l'evidenza di un altro permesso. Misura: `python3 tools/verdict.py` su tutti i permessi
del progetto, e `python3 tools/tests/test_ad_org.py` per la prova che il difetto, rimesso, fa
fallire il test.

## Data di revisione

2026-11-11

## Esito misurato

Da compilare il 2026-11-11: se i gate `INVALID` sono ancora 0 sui permessi esistenti, e se il test
che rimette il difetto e' ancora presente e fallisce.
