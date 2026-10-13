# DECISIONI — Decision Record

Registro delle decisioni di Livello 2 e 3. Fonte normativa: [GOVERNANCE-AZIENDALE.md](../GOVERNANCE-AZIENDALE.md).

Un file per decisione: `DECISIONI/DEC-<numero>-<slug>.md`. Il record è **immutabile**: non si riscrive, non si riordina, non si cancella. Una decisione successiva che cambia la precedente produce un **nuovo** record, che cita l'id di quello superato.

## Cosa deve contenere

Ogni record dichiara: problema, **opzioni con la fonte** incluso il non fare nulla, evidenze, scelta, approver, conseguenze, metrica, data di revisione e **esito misurato**.

`python3 tools/verbali.py check` verifica che il modello sia seguito. I verbali **prima di DEC-0037** sono esenti: sono record a mano libera e immutabili, e riscriverli per farli entrare in una regola nata dopo falsificherebbe la storia.

## Chi scrive cosa

L'orchestratore del dominio prepara il record. Per il Livello 3 decide il CEO,; per il Livello 2 decide l'orchestratore competente. Finché il record è in stato `proposto` la decisione **non è presa** e nessun agente può agire come se lo fosse.

Senza risposta entro 2 giorni lavorativi la proposta **non** è approvata.

## Regole

- Nessuna spesa fuori soglia, invio esterno, contratto, prezzo, identità di marca, assunzione, accesso in produzione o modifica irreversibile senza un record approvato.
- Il record non autorizza di per sé produzione, spesa o azioni esterne: autorizza la decisione.
- Un record non assegna task e non sostituisce un task contract.
- Le evidenze citate devono essere verificabili: un'assunzione non si presenta come fatto.

## Avvio rapido

```sh
cp DECISIONI/_TEMPLATE.md "DECISIONI/DEC-0003-<slug>.md"
```

## Indice

| Record | Oggetto | Livello | Stato |
|---|---|---|---|
| [DEC-0001](DEC-0001-approvazione-governance-v2.md) | Approvazione di GOVERNANCE AZIENDALE V2.0 | 3 | approvato |
| [DEC-0002](DEC-0002-layer-sempre-attivo.md) | Layer sempre attivo e fascia deterministica | 2 | approvato |
| [DEC-0003](DEC-0003-cervello-e-porta-dingresso.md) | Cervello in `.brain/`, porta d'ingresso, enforcement sulla shell | 2 | approvato |
| [DEC-0004](DEC-0004-analisi-evolutiva.md) | Dovere di analisi evolutiva per CEO e orchestratori | 3 | approvato |
| [DEC-0005](DEC-0005-la-richiesta-non-e-un-ordine.md) | La richiesta non è un ordine: ricerca, risposta, consenso | 3 | approvato |
| [DEC-0006](DEC-0006-sblocco-dominio-business.md) | Sblocco del dominio business: 13 specialisti assegnabili | 2 | approvato |
| [DEC-0007](DEC-0007-marcatore-di-approvazione.md) | Il consenso del CEO e' un atto depositato | 3 | approvato |
| [DEC-0008](DEC-0008-milestone-e-sprint.md) | Milestone e sprint: la storia documentata di ogni progetto | 3 | approvato |
| [DEC-0009](DEC-0009-artefatti-di-governance.md) | Gli artefatti di governance protetti come le cartelle prodotto | 3 | approvato |
| [DEC-0010](DEC-0010-provenienza-del-marcatore.md) | Provenienza del marcatore: lo scrive l'agente su mandato | 3 | approvato |
| [DEC-0011](DEC-0011-trapianto-meccanismi.md) | Trapianto dei meccanismi: etichette, side-effect, precedenza fonti | 2 | approvato |
| [DEC-0012](DEC-0012-registro-drift-e-protocollo.md) | Registro drift e i tre pezzi del protocollo | 2 | approvato |
| [DEC-0013](DEC-0013-vulnerabilita-marketing-factory.md) | Chiusura delle vulnerabilita' di AD-Marketing-Factory | 3 | approvato |
| [DEC-0014](DEC-0014-gate-locale-marketing-factory.md) | Riparazione del gate di verifica locale | 2 | approvato |
| [DEC-0015](DEC-0015-scanner-di-sicurezza.md) | Scanner di sicurezza indipendenti, installati come binari | 2 | approvato |
| [DEC-0016](DEC-0016-redazione-chat-history.md) | Redazione delle credenziali nel verbale storico | 3 | approvato |
| [DEC-0017](DEC-0017-commit-marketing-factory.md) | Commit delle modifiche verificate su AD-Marketing-Factory | 2 | approvato |
| [DEC-0018](DEC-0018-analisi-come-milestone.md) | L'analisi di un progetto e' una milestone, non un piano | 2 | approvato |
| [DEC-0019](DEC-0019-allineare-il-livello-sempre-caricato.md) | Allineare il livello sempre caricato a cio' che il sistema e' | 2 | approvato |
| [DEC-0020](DEC-0020-coherence.md) | Il livello sempre caricato si controlla da solo | 2 | approvato |
| [DEC-0021](DEC-0021-linguaggio-semplice.md) | A il CEO si parla in parole comprensibili | 2 | approvato |
| [DEC-0022](DEC-0022-punto-cieco-dipendenze.md) | Il punto cieco nel controllo delle dipendenze | 2 | approvato |
| [DEC-0023](DEC-0023-test-che-misurava-il-workspace.md) | Il test che misurava il workspace invece del codice | 2 | approvato |
| [DEC-0024](DEC-0024-carte-nel-progetto-e-bootstrap.md) | Le carte nel progetto, il bootstrap e il revisore indipendente | 2 | approvato |
| [DEC-0025](DEC-0025-carte-nel-progetto.md) | La super cartella tiene la macchina, non le carte | 2 | approvato |
| [DEC-0026](DEC-0026-riordino-repository-annidato.md) | Via il repository annidato, e i permessi che restano aperti | 2 | approvato |
| [DEC-0027](DEC-0027-date-inventate.md) | Le date inventate | 2 | approvato |
| [DEC-0028](DEC-0028-controllo-dopo-la-scrittura.md) | Il controllo che mancava: dopo la scrittura | 2 | approvato |
| [DEC-0029](DEC-0029-registro-errori.md) | Il registro delle cicatrici | 2 | approvato |
| [DEC-0030](DEC-0030-blueprint.md) | Il Blueprint | 2 | approvato |
| [DEC-0031](DEC-0031-prove-comportamentali.md) | Le prove comportamentali | 2 | approvato |
| [DEC-0032](DEC-0032-squadra-di-marca.md) | La squadra di marca, e i conteggi che invecchiano | 2 | approvato |
| [DEC-0033](DEC-0033-fotografia-col-sigillo.md) | La fotografia col sigillo | 2 | approvato |
| [DEC-0034](DEC-0034-fotografia-completa.md) | La fotografia inquadra la stanza intera | 2 | approvato |
| [DEC-0035](DEC-0035-il-letterale-e-il-difetto.md) | Il letterale e' il difetto | 2 | approvato |
| [DEC-0036](DEC-0036-meno-registri-piu-uso.md) | Meno registri, piu' uso | 2 | approvato |
| [DEC-0037](DEC-0037-il-modello-si-controlla.md) | Il modello dei verbali si controlla | 2 | approvato |
| [DEC-0038](DEC-0038-un-solo-motore-di-scrittura.md) | Un solo motore di scrittura | 3 | approvato |
| [DEC-0039](DEC-0039-cursor-non-e-una-superficie.md) | Cursor non e' una superficie da mettere sotto cancello | 3 | approvato |
| [DEC-0040](DEC-0040-il-verdetto-di-proporzione.md) | Il verdetto di proporzione | 2 | approvato |
| [DEC-0041](DEC-0041-sequenza-e-id.md) | La sequenza non si poteva eseguire, e gli id si scommettevano | 2 | approvato |
| [DEC-0042](DEC-0042-la-supercartella-e-un-repository.md) | La supercartella e' un repository | 3 | approvato |
