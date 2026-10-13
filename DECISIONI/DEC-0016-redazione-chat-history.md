# DEC-0016 — Redazione delle credenziali nel verbale storico e tracciamento del file

```yaml
id: DEC-0016
stato: approvato
livello: 3
data: 2026-10-08
approver: CEO
supera:
```

## Problema

`3. AD-Marketing-Factory/docs/chat-history.md` contiene **quattro credenziali** — tre JWT e una chiave API — ed e' **non tracciato e non ignorato da git**. Un `git add -A` le porterebbe in un commit, dove restano per sempre: un token in un commit non si cancella, si ruota.

Il file non e' un residuo. E' il **verbale grezzo della storia del progetto**: 365 conversazioni, 47.277 righe, 7,1 MB, con scambi Utente/Assistente e chiamate ai tool. E' citato da quattro documenti, tra cui `PROJECT_DOCUMENTATION_DRIFT.md`, che lo classifica come documento storico protetto da `INV-DOC-001`: *«era vero quando sono stati scritti e non vanno riscritti»*.

## Evidenze

- gitleaks 8.30.1: quattro ritrovamenti in `docs/chat-history.md` — tre `jwt` (348, 356, 360 caratteri) e un `generic-api-key` (44 caratteri).
- `git check-ignore` sul file: nessun esito. `git ls-files --cached --others --exclude-standard` lo include: e' committabile.
- **E' l'unico documento non tracciato su 118 in `docs/`.** Il progetto traccia tutti gli altri storici, compreso `APP_ANALYSIS_FULL_2026-10-06.md` che lo cita. Quindi quattro documenti **tracciati** citano un file che, dal repository, non esiste.
- `APP_ANALYSIS_FULL_2026-10-06.md:75` lo registra come «pre-esistente» e `:610` dichiara di averlo «campionato, non letto integralmente»: e' una fonte consultata, non un file operativo.
- I tre JWT hanno `iat` del 2026-09-19 e **nessun `exp`**. Non e' possibile stabilire se siano ancora validi, e non lo si dichiara.

## Opzioni

1. **Redigere e tracciare.**
2. Redigere e aggiungere a `.gitignore`.
3. Cancellare il file.
4. Lasciare com'e'.

## Scelta

**Opzione 1.** Le quattro stringhe diventano un segnaposto; una nota datata in testa al file dichiara cosa e' stato rimosso e perche'; il file viene tracciato con git.

Perche' **redigere** e non cancellare: il valore del transcript sta nel ragionamento, non nei token. Rimuovere le credenziali conserva tutto il resto, e la storia del progetto e' l'unica fonte primaria delle sue decisioni.

Perche' **tracciare** e non ignorare: il progetto traccia i propri storici. Lasciarlo fuori significherebbe lasciare quattro citazioni rotte in documenti tracciati — cioe' un riferimento a un artefatto che dal repository non esiste. Se il file va conservato, va conservato dove le citazioni lo trovano.

Perche' la redazione e' **visibile e datata**: una modifica silenziosa a un documento storico e' indistinguibile da una manomissione. La nota dichiara l'intervento, e chi legge sa che il transcript e' integro tranne quattro stringhe.

## Il contract, e perche' non e' GOV-000

L'operazione richiede un contract che copra il file. Non si estende `GOV-000`:

**Invariante 7 — un agente non modifica il proprio contract.** `GOV-000` e' il contract sotto cui l'agente opera, e il suo `write_scope` copre `.brain/` e `tools/`. Aggiungervi un percorso di progetto significherebbe che l'agente **allarga la propria autorita'** per toccare cio' che oggi non puo' toccare. E' il caso che l'invariante esiste per impedire.

C'e' anche una ragione di merito: un contract di governance non deve contenere percorsi di progetto. Un contenitore che accoglie tutto e' un contenitore senza confine.

Quindi: **`SEC-002`, su un solo file**, `write_scope: 3. AD-Marketing-Factory/docs/chat-history.md`.

## Conseguenze

- Le credenziali non sono piu' committabili.
- Il file diventa il 118esimo documento tracciato, e quattro citazioni smettono di essere rotte.
- La storia del progetto resta consultabile e integra, con l'intervento dichiarato.
- Esecutore `technical-writer` (`documentation`): il deliverable e' un documento, e la card **esclude `quality_verdict`**, quindi non puo' validare il proprio lavoro. Il gate `Security` resta alla card `security`.
- **Limite dichiarato**: la redazione interviene sul **working tree**, non sulla storia di git. Se il file fosse gia' stato committato in passato, le credenziali resterebbero nello storico. Verificato che non lo e' mai stato — ma la verifica vale per questo repository, non in generale.
- **Limite dichiarato, e importante**: rimuovere le credenziali da un file **non le disattiva**. I token restano validi nei sistemi che li hanno emessi. Tre JWT senza scadenza vanno **ruotati**, ed e' un'operazione separata che richiede accesso ai sistemi. Questo record non la copre, e non va letto come se il problema fosse risolto.

## Metrica

Segreti in file committabili di questo progetto: atteso zero, a parte i tre falsi positivi dichiarati (`dedupeKey`, `factKey`). E numero di token ruotati fra i quattro rimossi: atteso 4, oggi 0.

## Data di revisione

2026-11-07
