#!/usr/bin/env python3
"""Keyword retrieval over strategic_memory/index.json. Not a second vector database."""
import json, sys
from pathlib import Path
root = Path(__file__).resolve().parent
index = json.loads((root / "index.json").read_text())
query = " ".join(sys.argv[1:]).lower()
tokens = [t for t in query.replace("/", " ").replace(",", " ").split() if len(t) > 2]
syn = {
    "posizionamento": "positioning", "segmentazione": "segmentation", "saas": "saas",
    "b2b": "b2b", "vendita": "sales", "persuasione": "persuasion", "scoperta": "discovery",
}
tokens += [syn[t] for t in list(tokens) if t in syn]
# Espansione controllata solo per intenti già nominati dalla specifica. Non è un embedding.
if "positioning" in tokens or "saas" in tokens:
    tokens += ["segmentation", "customer-value", "differentiation", "b2b", "discovery", "persuasion", "sales", "marketing-strategy"]
scored = []
for item in index:
    hay = " ".join([item["author"], item["area"], " ".join(item["topics"])]).lower()
    score = sum(1 for t in tokens if t in hay)
    if score:
        scored.append((score, item))
scored.sort(key=lambda x: -x[0])
for score, item in scored[:8]:
    print(f"{score}\t{item['area']}\t{item['author']}\t{item['path']}")
if not scored:
    print("NO_MATCH")
