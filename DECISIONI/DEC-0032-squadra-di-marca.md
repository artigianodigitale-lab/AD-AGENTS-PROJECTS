# DEC-0032 — La squadra di marca, e i conteggi che invecchiano

```yaml
id: DEC-0032
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera:
```

## Problema

Il CEO ha chiesto una squadra di agenti per **brand identity, archetipal branding, proto-personas
e analisi competitor**, attivabile **solo su chiamata**.

Io gli ho risposto: *«hai ragione, non esiste»*. Mi basavo su una ricerca di parole chiave —
`competitor` compariva **0 volte**, `posizionamento` **0 volte**.

**Era falso.** Le schede `lb-brand-identity`, `lb-archetypal-branding` e `lb-personas`
**esistevano già**, con Aaker, Kapferer e Jobs to Be Done dentro. Non comparivano solo perché
**non usano quelle parole**.

L'ha scoperto il registry rifiutando l'inserimento: *«id duplicato: lb-personas»*.

## Scelta

**Non aggiungere doppioni: arricchire quello che c'è, e aggiungere solo il mancante.**

| Scheda | Cosa è cambiato |
|---|---|
| `lb-brand-identity` | già con Aaker e Kapferer. Aggiunti: **la regola di scelta** fra i due (B2C emotivo → Kapferer; B2B, razionale, legato al prodotto → Aaker) e **i due modelli** — oggi e domani — perché entrambi sono statici |
| `lb-archetypal-branding` | aggiunto: i 12 di Mark & Pearson **non reggono**, i consumatori ne percepiscono **quattro**; quindi **tensione, non etichetta**, e **dedotta** dagli altri passi |
| `lb-personas` | aggiunto: **falsificabilità obbligatoria** — ipotesi, conferma, smentita, e se i dati esistono. Più il percorso utente, senza il quale le personas non dicono nulla sul comportamento |
| `lb-competitors` | **nuova**. Porter + mappa + smontaggi |
| `lb-positioning` | **nuova**. La frase, e la prova dal lato cliente |

E la procedura `ad-brand-team`, con la sequenza a 8 passi e **i metodi con le fonti dentro**.
Si attiva solo su chiamata, e non produce slide: produce un **Blueprint di marca**.

Registry: **42 card** (26 tecniche, 16 business).

## Il secondo problema, trovato correggendo il primo

Aggiungendo due schede, il numero è rimasto vecchio in **sei posti** — costituzione, tre skill,
il vocabolario. Nessun controllo lo leggeva.

Ho scritto `conteggi_delle_card` in `ad_coherence.py`. **E non funzionava:**

1. `ad_registry.load()` non accetta argomenti → la chiamata sollevava → il mio
   `except Exception: return []` **inghiottiva l'errore in silenzio**. Il controllo non
   controllava niente, e sembrava una difesa.
2. Corretto quello, ne è emerso un secondo: `load()` restituisce un **dizionario**, e iteravo le
   chiavi — contava zero di tutto.
3. E le mie correzioni erano sbagliate: avevo scritto «16 specialisti» quando 16 è il **totale**
   business. Gli specialisti sono **15**.

Ora usa le stesse funzioni di `cards.py check` (`by_domain`), così il numero è **uno solo**, e
l'errore del registry **si dice** invece di essere nascosto. Provato: mettendo `40` al posto di
`42` in una skill, il controllo lo prende.

## Evidenze

- `tools/cards.py check` → 42 card, 0 problemi bloccanti
- `python3 tools/cards.py match competitor_analysis` → `lb-competitors`; `positioning` →
  `lb-positioning`; `brand_model_selection` → `lb-brand-identity`
- `ad_coherence.py` con il controllo dei conteggi, **provato a fallire**
- I due errori registrati: `ERR-0010` (cercare una parola e concludere che non c'è) e
  `ERR-0011` (un controllo che non poteva fallire)
- Test della suite: **211 controlli**

## La lezione, ed è la terza volta in tre giorni

`ERR-0010` è **la terza volta** che sbaglio misurando la cosa sbagliata:

| Errore | Cosa ho misurato | Cosa dovevo misurare |
|---|---|---|
| `ERR-0002` | `.git` con `-type d` — le cartelle | i file **e** le cartelle |
| `ERR-0009` | se il file **esiste** | cosa il file **dichiara** |
| `ERR-0010` | le **parole** dentro le schede | le **schede** |

**Una ricerca per parola chiave trova le parole, non le cose.** Ora è scritto.

E `ERR-0011` insegna la regola che avevo appena scritto e non applicato: **la prova va fatta sul
controllo nuovo, non su quello vecchio.** Un controllo che non ho mai visto fallire non è un
controllo — l'ho scritto in `evals/README.md` e poi non l'ho fatto.

## Conseguenze

- La squadra di marca esiste, con i metodi e i limiti documentati in `ad-brand-team`.
- **Nessun doppione**: tre schede arricchite invece di tre nuove.
- **Sei numeri vecchi corretti**, e un controllo che non li lascerà invecchiare.
- `ERR-0010` e `ERR-0011` nel registro.

## Limiti dichiarati

- **I libri di Aaker, Kapferer e Keller non li abbiamo letti.** Abbiamo letto come li descrivono
  fonti accademiche che li citano con le pagine.
- **La tesi sugli archetipi è una sola**; **lo studio 2025 è su 75 persone su LinkedIn**;
  **Chapman & Milham l'abbiamo letto solo in abstract**; **le critiche a Keller non le abbiamo
  lette** (a pagamento, e Cloudflare ha fermato anche il browser).
- **Il controllo dei conteggi guarda solo `.brain/`.** Un numero vecchio in un documento
  normativo della radice non lo prende: si aggiorna lo snapshot a mano, ed è un buco noto.

## Metrica

Card nel registry: atteso **42** — e ora è un numero che il sistema verifica, non che qualcuno
ricorda.

## Data di revisione

2026-11-09
