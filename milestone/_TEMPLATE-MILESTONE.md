# Milestone {{MILESTONE}} — <titolo>

```yaml
progetto: {{PROGETTO}}
milestone: {{MILESTONE}}
stato: aperta            # aperta | chiusa
aperta: <AAAA-MM-GG>
chiusa:
obiettivo: "{{OBIETTIVO}}"
```

## Obiettivo della milestone

<Cosa deve esistere alla fine di questa milestone, con un esito misurabile.>

## Cosa rende questa milestone "prodotto finito"

<Il criterio per cui, chiusa questa milestone, il progetto e' ufficialmente un
prodotto e non piu' un cantiere. Se non e' l'ultima, dillo: e' un passo.>

## Sprint

| Sprint | Obiettivo | Stato | Prompt | Report |
|---|---|---|---|---|
| 1 | | | | |

## Report step by step

<La cronologia della milestone, in ordine. Per ogni passo: cosa si e' fatto, cosa
e' cambiato rispetto al piano, e il rimando al report dello sprint.>

1.

## Cosa resta fuori

<Cio' che e' emerso e non appartiene a questa milestone. Diventa la milestone
successiva o un Decision Record.>

## Verifica di chiusura

- [ ] ogni sprint ha `PROMPT.md` e `REPORT.md`
- [ ] la numerazione degli sprint e' contigua
- [ ] il lavoro e' stato verificato da chi non l'ha prodotto
- [ ] le evidenze dei gate richiesti sono depositate
- [ ] `python3 tools/milestone.py check "<progetto>"` non segnala nulla
