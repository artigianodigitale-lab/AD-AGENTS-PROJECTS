# contratti — contract operativi del layer di enforcement

Un file per task: `contratti/<TASK_ID>.yaml`. E' il task contract di
[TASK-CONTRACTS.md](../TASK-CONTRACTS.md) **piu'** il campo `write_scope`, che
dichiara dove quel task puo' scrivere.

Questi file sono l'autorita' del layer di enforcement di runtime (`DEC-0003`):
il plugin DSH chiede a `tools/contract_scope.py` se un percorso e' coperto, e
non reimplementa la regola.

## Cosa sono protette

Solo le **cartelle prodotto numerate** della root: `5.APP-Artigiano-Digitale`,
`11. Modelbel`, `3. AD-Marketing-Factory` e cosi' via. Tutto il resto — i
documenti di root, `tools/`, `DECISIONI/`, `REQUISITI/`, `comunicazioni/`,
`strategic_memory/`, `tests/` — resta scrivibile senza contract: e' il lavoro di
governo, non il lavoro di prodotto.

## Regole

- Un percorso protetto si scrive **solo** se un contract attivo lo copre.
- `status` ammessi: `active`, `attivo`, `approvato`. Qualsiasi altro valore non
  copre.
- `write_scope` elenca prefissi di directory o file, relativi alla root di
  `AD Projects`. Un contratto copre un percorso se coincide o sta sotto un
  prefisso elencato.
- `expires` (opzionale, ISO 8601) rende il contract non coprente dopo quella
  data.
- Un contract senza `write_scope` non copre nulla: non e' un errore, e' un
  contratto che non autorizza scritture.

## Cosa NON copre questo layer

- **Le scritture via shell sono coperte solo in parte.** Il plugin riconosce le
  mutazioni evidenti su un percorso di progetto — `rm`, `mv`, redirezioni,
  `sed -i`, `git checkout`, installazioni di pacchetti — e blocca anche quelle.
  Ma e' un'**euristica**: un comando che cambia directory con `cd` e poi scrive in
  modo relativo puo' sfuggirle. Il confine affidabile resta `write_scope`, non
  l'analisi della shell.
- **La verifica dell'evidenza.** Dichiara un ambito, non giudica il lavoro:
  quello resta al Quality Gate.
- **I permessi per-card.** Un contract puo' aprire un ambito anche a una card
  che, per il proprio registry, non lo coprirebbe. Il controllo card-per-card lo
  fa `tools/validate_contract.py` sul contract completo.

## Flusso

```text
Lead scrive contratti/<TASK_ID>.yaml
        |
        v
l'agente prova a scrivere in una cartella prodotto
        |
        v
il plugin chiede: python3 tools/contract_scope.py check <path>
        |
   coperto -> la scrittura procede
   non coperto -> la scrittura si ferma, con il rimedio nel messaggio
```

## Comandi

```sh
python3 tools/contract_scope.py check "5.APP-Artigiano-Digitale/src/api/x.ts"
python3 tools/contract_scope.py list
python3 tools/contract_scope.py policy
```

## Avvio rapido

```sh
cp contratti/_TEMPLATE.yaml "contratti/PROD-000.yaml"
```
