# DEC-0009 — Gli artefatti di governance sono protetti come le cartelle prodotto

```yaml
id: DEC-0009
stato: approvato
livello: 3
data: 2026-10-08
approver: CEO
supera:
```

## Problema

L'enforcement proteggeva le **cartelle prodotto** — i percorsi che iniziano con un numero — e non gli artefatti che **definiscono ed eseguono le regole**. Verificato il 2026-10-08: `.brain/` e `tools/` rispondevano «fuori dalle cartelle prodotto», quindi liberamente scrivibili senza contract e senza consenso.

La catena che ne deriva:

```text
.brain/COSTITUZIONE.md  ->  ~/.dsh/AGENTS.md       -> istruzioni in OGNI sessione
.brain/skills/ad-*      ->  ~/.agents/skills/ad-*  -> procedure in OGNI sessione
.brain/plugin/...mjs    ->  profilo DSH            -> l'enforcement stesso
tools/ad_scope.py       ->  l'autorita' interrogata dal plugin
```

Tre conseguenze, tutte verificate:

1. **Auto-referenzialita'.** Un agente poteva riscrivere `index.mjs` e disattivare l'enforcement che blocca le scritture. La regola poteva modificare se stessa.
2. **Esecuzione arbitraria.** `settings.json`, scrivibile (664), controlla `checker` e `python`, che finiscono in `spawnSync`: puntandoli altrove si esegue codice arbitrario nel processo host di DSH.
3. **Raggio d'azione globale.** Una scrittura in `.brain/` non tocca un progetto: cambia il comportamento di **tutti** gli agenti, in **ogni** sessione, anche fuori da AD Projects.

Causa: il confine era stato definito sulla *forma del nome* (`^\d+\.`), non sul *raggio d'azione*. Un artefatto globale risultava meno protetto di un progetto locale.

## Opzioni

1. Proteggere `.brain/` e `tools/` con la stessa autorita' delle cartelle prodotto.
2. Proteggere anche `contratti/`, `approvazioni/`, `DECISIONI/`, `piani/`.
3. Solo lo snapshot di integrita', senza enforcement.
4. Non fare nulla.

## Evidenze

- `contract_scope.py check` il 2026-10-08: `.brain/COSTITUZIONE.md`, `.brain/skills/...`, `.brain/plugin/.../index.mjs`, `tools/ad_scope.py` → tutti «OK, fuori dalle cartelle prodotto».
- `settings.json` modo 664, con i campi `checker` e `python` consumati da `spawnSync` senza validazione.
- Symlink verificati: `~/.dsh/AGENTS.md` → `.brain/COSTITUZIONE.md`; `~/.agents/skills/ad-*` → `.brain/skills/ad-*`; plugin montato dal profilo.
- Limite dichiarato nel plugin: l'analisi della shell e' un'euristica. Un varco sugli artefatti che la eseguono e' un varco sull'insieme.

## Scelta

**Opzione 1.** `.brain/` e `tools/` diventano una seconda classe protetta, con la stessa regola: serve un contract attivo con `write_scope` che copre il percorso, **e** il marcatore di approvazione del CEO.

**Opzione 2 e' stata scartata per un motivo tecnico, non di merito**: `contratti/` e `approvazioni/` sono l'**input** dell'autorizzazione. Proteggerli impedisce di creare il primo contract, e il sistema non parte piu'. La deroga e' dichiarata nel contract stesso, tra i vincoli.

## Conseguenze

- La porta che rendeva aggirabile ogni altra regola e' chiusa.
- **Il sistema ha bloccato il suo autore.** La protezione e' entrata in vigore nell'istante del salvataggio — il plugin avvia un processo Python nuovo a ogni controllo, quindi non serve un riavvio — e ha rifiutato la modifica successiva di `tools/ad_scope.py`. Il bootstrap e' stato risolto con il contract `GOV-000`, non aggirando il controllo.
- Lo stato e' stato reso esplicito: la protezione agisce sui tool di scrittura **prima** che su `bash_target`. Nella finestra intermedia `rm -rf .brain/skills` sarebbe passato. Dichiararlo e' parte della scelta.
- Modificare il cervello ora richiede una decisione tracciata. Anche per il Lead.
- **Limite dichiarato**: restano fuori `DECISIONI/`, `piani/`, `EVOLUZIONE/`, `comunicazioni/` e i documenti di root. Le prime tre sono coperte dallo snapshot di integrita' e dall'obbligo di Decision Record; i documenti di root dal gate `tests/test_strategic_memory.py`. Non e' la stessa garanzia dell'enforcement, ed e' un residuo noto.

## Metrica

`contract_scope.py check` su un percorso di `.brain/` e uno di `tools/` senza contract: atteso 1 su entrambi. E numero di scritture di governance respinte: oggi 1, la mia.

## Data di revisione

2026-11-07
