# DEC-0010 — La provenienza del marcatore di approvazione

```yaml
id: DEC-0010
stato: approvato
livello: 3
data: 2026-10-08
approver: CEO
supera:
modifica: DEC-0007
```

## Problema

DEC-0007 stabiliva che il marcatore di approvazione lo crea **il CEO**, e che un agente che scrive il proprio marcatore falsifica un atto di governance. La regola e' tecnicamente corretta e operativamente insostenibile: per ogni lavorazione sarebbe servito un intervento manuale di scrittura YAML.

Il CEO ha deciso diversamente, con queste parole:

> *forse e' meglio che non generi io un marcatore ma che lo generi tu se ti serve. Prima passi da me e io ti approvo e tu continui*

## Opzioni

1. **L'agente scrive il marcatore** dopo un'approvazione esplicita in chat, citando la frase del CEO in un campo `fonte`.
2. **Solo il CEO lo scrive**, come in DEC-0007.
3. Marcatore scritto dall'agente senza citare la fonte.

## Evidenze

- Il primo tentativo reale e' fallito: per completare la protezione di `.brain/` serviva un contract, per il contract serviva il marcatore, e il marcatore richiedeva un intervento manuale del CEO. Il sistema si e' fermato su un requisito di forma, non su un dubbio di merito.
- L'opzione 2 e' quella che DEC-0007 prescriveva, ed e' quella che ha bloccato il lavoro.
- Un controllo tecnico che richiede un intervento manuale a ogni giro non viene usato: viene aggirato o disattivato.

## Scelta

**Opzione 1.** L'agente scrive il marcatore su indicazione esplicita del CEO, dopo che l'approvazione e' avvenuta **in chat**, e il marcatore porta:

- `fonte`: la frase esatta con cui il CEO ha approvato;
- `fonte_delega`: la frase con cui ha delegato la scrittura, quando esiste;
- e in testa al file, un commento che dichiara la provenienza e la sua debolezza.

## Conseguenze

- Il flusso non si blocca piu' su un requisito di forma.
- **Il marcatore e' piu' debole, e va detto**: prova che l'agente ha eseguito un comando, non che il CEO ha approvato. La verifica si sposta sulla **conversazione**, che resta la fonte primaria.
- La regola di DEC-0007 «un agente non approva se stesso» resta valida nella sostanza: l'agente scrive il marcatore **dopo** e **su mandato**, mai di propria iniziativa, e non puo' scegliere il contenuto dell'approvazione.
- Un `fonte` vuoto o inventato e' verificabile: la frase deve esistere nella conversazione. Chi rilegge puo' contestarlo.
- Resta vietato, senza deroga: scrivere un marcatore **prima** che il CEO abbia approvato, e scriverne uno per un lavoro che il CEO non ha approvato.
- Primo marcatore prodotto con questa regola: `approvazioni/GOV-000.yaml`.

## Limite dichiarato

Il campo `fonte` e' una citazione, non una firma: nessun controllo automatico verifica che la frase esista davvero. La garanzia e' documentale e retrospettiva. **Non misuro questo limite come risolto**: lo registro come il costo accettato dell'opzione 1.

## Metrica

Numero di marcatori con `fonte` compilata e verificabile (atteso: 100%). E numero di marcatori revocati dopo contestazione della fonte: atteso zero, e un valore diverso da zero segnala che la regola non regge.

## Data di revisione

2026-11-07
