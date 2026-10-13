# REQ-<numero> — <oggetto>

```yaml
id: REQ-<numero>
stato: proposto            # proposto | approvato | superato
data: <AAAA-MM-GG>
decision_record: DEC-<numero>   # obbligatorio: senza record approvato non è approvato
product:                   # artigiano-digitale | ad-stock-tracker | biocimatica | altro
gate_previsti: []          # gate di dominio business pertinenti (Strategy, Brand, Legal, GDPR, Finance)
```

## Cosa

<Il bisogno in una frase, dal punto di vista di chi lo riceve.>

## Perché

<Il problema di business e la sua evidenza.>

## Per chi

<Segmento, persona, cliente o utente interno interessato.>

## Criteri di accettazione

- <osservabile e verificabile>

## Fuori scope

- <cosa non è incluso>

## Vincoli noti

- <legge, privacy, budget, scadenze, compatibilità>

## Requisiti tecnici derivati

| Contract | Dominio | Card | Stato |
|---|---|---|---|
| _da assegnare da LB-MASTER ORCHESTRATOR_ | technical | — | — |
