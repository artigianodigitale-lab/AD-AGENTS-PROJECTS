# errori — le cicatrici che il sistema cita ancora

**Questo registro e' curato, non completo.** Un registro che si dichiara completo quando non
lo e' e' peggio di un registro piccolo: chi legge non sa cosa gli manca.

## Il criterio, e il suo limite

**Resta una cicatrice se il sistema la cita** — una regola, un controllo, una prova, un nota,
il registro drift, un contratto. Le fonti sono **il sistema**, non i registri: cercare le
citazioni dentro `errori/` le troverebbe tutte, perche' **le cicatrici si citano fra loro**,
e allora non si toglierebbe mai niente.

**Ma il criterio da solo non basta, e il 2026-10-13 me ne sono accorto tardi:** una cicatrice
**nuova** non e' ancora citata da nessuno — quindi verrebbe cancellata subito, e il registro
**non potrebbe mai crescere**. `ERR-0048` e' sparita esattamente cosi'.

Quindi si tiene anche cio' che e' **nato dal lavoro sulla macchina stessa**, e non dai
progetti. E' per questo che il criterio si e' dovuto correggere **tre volte** in un giorno:
la prima versione cercava le citazioni dentro i registri, la seconda non lasciava crescere
il registro. **Un criterio sbagliato si vede solo eseguendolo.**

## Cosa c'e' dentro

Le cicatrici **che il sistema nomina ancora** — una regola, un controllo, una prova, una nota.
Sono quelle che hanno lasciato qualcosa: `ERR-0004` e' l'ordine del consenso, `ERR-0026` e' il
confine delle scritture, `ERR-0024` e' lo spostamento di una cartella senza guardare dove
finiva.

## Cosa non c'e', e perche'

Il resto era la **cronaca di giorni di lavoro**: sessanta cicatrici in quattro giorni, quasi
tutte nate e chiuse nello stesso pomeriggio. Servivano a me, mentre succedevano.

**E molte sono diventate un controllo.** Questa e' la regola del sistema: *un errore si
registra, e se si puo' meccanizzare diventa un controllo* — e da quel momento e' **impossibile**,
non «sconsigliato». Da allora il file non serve piu': serve il controllo, che fallisce.

Per esempio:

| Era una cicatrice | Adesso e' |
|---|---|
| due sessioni scelsero lo **stesso id** | `ad_docs.prenota_id()`, atomico sul filesystem |
| un verbale senza le opzioni e senza il «non fare nulla» | `verbali.py check` |
| rapporti di passo senza le sei sezioni | `milestone.py check` |
| un CAPTCHA scambiato per una pagina da leggere | il **muro** in `ricerca.py` |
| un 403 letto come «link morto» | `verifica` distingue 404 da 403 |
| un progetto senza numero passava il cancello | il blocco in `ad_scope.py` |

## E una cosa che non si dice

**Non si dice che ogni cicatrice tolta sia diventata una regola.** Non e' vero: alcune erano
solo giorni difficili, e la loro lezione e' rimasta nella testa di chi c'era.

Si dice quello che si puo' verificare: **le cicatrici rimaste sono quelle che il sistema cita**,
e le altre non servivano piu' a decidere niente.
