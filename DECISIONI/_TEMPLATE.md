# DEC-<numero> — <oggetto>

```yaml
id: DEC-<numero>
stato: proposto            # proposto | approvato | respinto | superato
livello: 3                 # 2 = orchestratore competente | 3 = il CEO
data: <AAAA-MM-GG>
approver: CEO             # chi decide
supera:                    # id del record precedente, se esiste
```

## Problema

<Cosa va deciso, perché ora, e cosa succede se non si decide.>

## Opzioni

1. **<opzione A>** — <conseguenza, costo, rischio> — fonte: <URL, data>
2. **<opzione B>** — <conseguenza, costo, rischio> — fonte: <URL, data>
3. **Non fare nulla** — <conseguenza. E' l'opzione di riferimento: senza, non si sa
   con cosa si sta confrontando la scelta>

## Evidenze

- <dato, test, misura, documento o Decision Record collegato>

## Scelta

<Opzione scelta e ragione. Se respinto, dirlo qui.>

## Conseguenze

- <effetto su prodotti, agenti, tempi, costi, permessi>

## Metrica

<Come si misura che la decisione ha funzionato.>

## Data di revisione

<AAAA-MM-GG>

## Esito misurato

<Da compilare alla data di revisione: cosa e' cambiato davvero, con quale evidenza.
Vuoto qui, a revisione passata, e' un errore — `python3 tools/verbali.py check`>
