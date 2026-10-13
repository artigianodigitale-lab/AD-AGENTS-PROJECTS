# Piano — <oggetto>

```yaml
id: PIANO-<numero>
stato: proposto            # proposto | approvato | corretto | respinto
data: <AAAA-MM-GG>
progetto: ""               # cartella numerata esistente, oppure "nuovo: <n>. <Nome>"
dominio: business          # business | tecnico
richiesta: ""              # la richiesta del CEO, in una riga
esito_ricerca: ""          # confermata | modificata | sconsigliata
decision_record: ""        # se serve una decisione di Livello 2 o 3
```

## 1. Cosa hai chiesto

<La richiesta del CEO, riformulata. Non le sue parole: l'obiettivo.>

## 2. Cosa ho trovato

<L'esito della ricerca sul metodo. Esiste un modo migliore, piu' scalabile, piu'
affidabile? Con fonti: URL e data di consultazione. Se non esiste, dirlo
esplicitamente.>

## 3. Cosa consiglio

<La raccomandazione. Puo' essere: la richiesta va bene cosi' | conviene
cambiarla | conviene non farla. Con la ragione e il costo.>

## 4. Cosa serve da te

<Il consenso richiesto, in una domanda secca.>

---

Solo dopo il consenso, le sezioni operative.

## Obiettivo

<Cosa deve esistere alla fine, con un esito misurabile.>

## Ambito

Cartelle e file toccati. Per un progetto nuovo: il nome della cartella da creare.

```text
write_scope previsto:
  - <percorso>
```

## Card coinvolte

| Card | Perche' | Task type |
|---|---|---|
| `<id>` | | |

Se nessuna card copre il lavoro: **STOP**, si dichiara qui e si chiede una card
nuova o un Transient Worker.

## Contract da aprire

| task_id | card | write_scope | gate richiesti |
|---|---|---|---|
| | | | |

## Gate e indipendenza

Chi verifica e' **diverso** da chi scrive.

| Gate | Owner dell'evidenza |
|---|---|
| | |

## Decisioni richieste al CEO

- <decisione, livello 2 o 3, e cosa cambia se si dice no>

## Rischi e dipendenze

- <rischio, dipendenza esterna, ordine dei passi>

## Costo previsto

Fascia di `MODEL-ROUTING.md` e modello. Eventuale spesa: importo e copertura.

## Fuori scope

- <cosa non e' incluso>

## Approvazione

```yaml
approvato_da:              # il CEO
data_approvazione:
note:
```
