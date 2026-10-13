# approvazioni — il consenso del CEO

Un file per task: `approvazioni/<TASK_ID>.yaml`. E' **l'atto con cui il CEO approva** un piano.

Un contract in `contratti/` **non copre nulla** finche' non esiste il marcatore corrispondente. Il plugin di enforcement interroga `tools/contract_scope.py`, che pretende entrambi:

```text
contratti/<TASK_ID>.yaml      status attivo + write_scope non vuoto
approvazioni/<TASK_ID>.yaml   task_id + approvato_da + data
        |
        v
il percorso e' coperto, la scrittura procede
```

## L'ordine conta

L'approvazione deve **precedere** il contract. Un contract scritto prima del consenso non copre: il controllo confronta le date di modifica dei due file e rifiuta l'ordine inverso.

```text
ricerca -> risposta al CEO -> CONSENSO (questo file) -> contract -> lavoro
```

Serve a impedire una cosa sola, ma importante: **retrodatare un contract** per far sembrare che il consenso ci fosse. Un contract preparato prima e attivato dopo e' esattamente cio' che la governance vieta.

## Chi lo crea

**Lo crea il CEO.** Un agente che scrive il proprio marcatore di approvazione non sta approvando nulla: sta falsificando un atto di governance.

Il marcatore non e' una firma crittografica: con un solo utente di sistema e un agente che ha accesso alla shell, la falsificazione non e' tecnicamente impossibile. Serve a rendere il consenso un **atto esplicito, datato e nominato**, e a rendere l'abuso un fatto visibile e provabile invece di un'assunzione implicita. E' il massimo che questa configurazione permette, ed e' meglio di prima.

## Campi obbligatori

| Campo | Perche' |
|---|---|
| `task_id` | deve coincidere con il contract |
| `approvato_da` | un'approvazione anonima non e' un'approvazione |
| `data` | serve a verificare l'ordine |

Un marcatore senza uno di questi campi **non vale**: viene ignorato e il contract resta non coprente.

## Comandi

```sh
python3 tools/contract_scope.py policy          # contract e approvazioni, con lo stato
python3 tools/contract_scope.py check "<percorso>"
```

## Avvio rapido

```sh
cp approvazioni/_TEMPLATE.yaml "approvazioni/<TASK_ID>.yaml"
```
