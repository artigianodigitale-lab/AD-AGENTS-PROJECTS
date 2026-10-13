# Piano — L'analisi è una milestone, non un piano

```yaml
task_id: ORG-001
data: 2026-10-08
stato: approvato
livello: 2
```

## 1. Cosa hai chiesto

Cinque modifiche perche' il cervello impari che l'analisi di un progetto produce una **milestone con i suoi sprint**, e che non si lavora prima.

## 2. Cosa ho trovato

Il sistema milestone esiste, ma **non e' nella sequenza che il cervello segue**. Ci sono due sequenze e non dicono la stessa cosa:

| Livello | Caricamento | Passi |
|---|---|---|
| Costituzione | sempre | 10, **senza** milestone |
| Skill `ad-kickoff` | a chiamata | 12, **con** milestone |

Nella costituzione "milestone" compare due volte: una cartella in una tabella e un comando fra gli strumenti. Mai come passo obbligatorio.

**Causa**: ieri ho costruito il sistema e l'ho messo nel livello a chiamata invece che nel livello sempre caricato. Il testo che decide e' quello gia' in memoria.

**Causa seconda**: ho interpretato il tuo consenso come autorizzazione a lavorare. L'oggetto del consenso era sbagliato — doveva essere la milestone.

## 3. Cosa consiglio

Tre livelli, in ordine di forza: costituzione (necessaria, debole), invariante (citabile), **meccanismo** (l'unico che lega). La lezione della giornata: il buco in `.brain/` l'abbiamo chiuso con un controllo, non con una raccomandazione.

## 4. Cosa serve da te

Il marcatore per `ORG-001`.

## 5. Ambito di scrittura

```yaml
write_scope:
  - ".brain/"
  - "tools/"
```

## 6. Passi

1. Costituzione: sequenza a 12 passi, invariante 13.
2. `TASK-CONTRACTS.md`: `milestone` e `sprint` obbligatori per i contract di progetto.
3. `ad_contract.py`: violazione se mancano, o se il `PROMPT.md` dello sprint non esiste.
4. `ad-kickoff`: il consenso diventa «il CEO approva le milestone».
5. Test: un contract su un progetto senza sprint aperto **deve** essere rifiutato.

## 7. Fuori ambito

Nessuna modifica ai contract esistenti, nessun tocco ai progetti, nessun ricalcolo delle lavorazioni di oggi in retrospettiva.
