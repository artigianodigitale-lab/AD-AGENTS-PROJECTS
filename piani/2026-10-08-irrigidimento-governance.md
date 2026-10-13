# Piano — Irrigidimento della governance e trapianto dei meccanismi

```yaml
task_id: GOV-000
data: 2026-10-08
stato: approvato
livello: 2
```

## 1. Cosa hai chiesto

Quattro decisioni, approvate tutte:

1. Proteggere gli artefatti di governance: scriverli richiede contract e marcatore.
2. Chiudere le sei vulnerabilita' del progetto `3. AD-Marketing-Factory`, di cui una RCE critica.
3. Installare gli scanner di sicurezza assenti.
4. Trapiantare i meccanismi trasferibili del Continuity Pack.

## 2. Cosa ho trovato

- `.brain/` e' symlinkato in `~/.dsh/AGENTS.md`, `~/.agents/skills/` e montato nel profilo DSH: chi scrive li' controlla ogni agente, in ogni sessione. Non era protetto.
- `settings.json` del plugin e' scrivibile e controlla `checker` e `python` di `spawnSync`: esecuzione arbitraria nel processo host.
- `npm audit` sul progetto: 6 vulnerabilita' di produzione, 1 critica (`next`, RCE in `next/og`), 5 alte (`prisma`, `@prisma/config`, `deepmerge-ts`, `sharp`, `source-map-js`).
- Nessuno scanner installato: gitleaks, semgrep, trivy, syft, osv-scanner, pip-audit assenti.
- Il pack del progetto e' documentario al 100%: nessuno script legge i suoi registri. Tre meccanismi valgono il trapianto.

## 3. Cosa consiglio

Chiudere la falla per prima: e' una escalation di privilegi e rende ogni altra regola aggirabile. Poi i meccanismi, che sono la cassetta degli attrezzi. Poi la RCE, che ha un fix disponibile. Gli scanner quando decidi sugli strumenti.

## 4. Cosa serve da te

Il marcatore di approvazione per questo task. Su tua indicazione lo scrive l'agente, con la tua frase verbatim nel campo `fonte`.

## 5. Ambito di scrittura

```yaml
write_scope:
  - ".brain/"
  - "tools/"
```

Fuori ambito: i documenti di root (coperti dallo snapshot e dal Decision Record), le cartelle prodotto, e `3. AD-Marketing-Factory` (che avra' un contract proprio).

## 6. Passi

1. Protezione degli artefatti di governance in `ad_scope.py` — **fatto** (attivo su write/edit).
2. Estensione a `bash_target` — **da fare**: senza, `rm -rf .brain/skills` passa ancora.
3. Test della nuova classe + correzione del test che asseriva `tools/` libero.
4. Trapianto C1 (etichette d'evidenza), C3 (dichiarazione side-effect), C4 (precedenza fonti).
5. Registro drift (C2) e i tre pezzi del protocollo: scala P0-P4, `impact_forecast`, vocabolario di risposta.
6. Decision Record, snapshot, verifica completa.
7. Contract separato per la RCE nel progetto.

## 7. Fuori ambito, dichiarato

Il marcatore scritto dall'agente e' piu' debole di un atto del CEO. Mitigazione: campo `fonte` con la frase esatta. Chi rilegge puo' confrontarla.
