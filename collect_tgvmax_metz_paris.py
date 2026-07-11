#!/usr/bin/env python3
"""
Collecteur TGVmax Metz <-> Paris.
Capture l'etat J..J+30 du dataset SNCF (ecrase chaque matin, aucun historique
officiel) et l'ecrit dans data/<capture_date>.csv, horodate.

Un fichier par jour = append-only, versionnable git sans conflit.
Lance 1x/jour apres la MAJ SNCF (debut de matinee).
"""

import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/records"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
WHERE = (
    '(origine="METZ VILLE" AND destination LIKE "PARIS") '
    'OR (origine LIKE "PARIS" AND destination="METZ VILLE")'
)
FIELDS = [
    "capture_date", "travel_date", "days_to_dep", "train_no",
    "origine", "destination", "heure_depart", "heure_arrivee", "happy_card",
]


def fetch_all():
    rows, offset, limit = [], 0, 100
    while True:
        qs = urllib.parse.urlencode({
            "where": WHERE, "limit": limit, "offset": offset,
            "order_by": "date,heure_depart",
        })
        req = urllib.request.Request(f"{BASE}?{qs}", headers={"User-Agent": "tgvmax-collector"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        batch = data.get("results", [])
        rows.extend(batch)
        offset += limit
        if offset >= data.get("total_count", 0) or not batch:
            break
    return rows


def main():
    today = dt.date.today()
    rows = fetch_all()
    if not rows:
        print("AUCUNE donnee renvoyee - filtre ou API a verifier", file=sys.stderr)
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    out = os.path.join(DATA_DIR, f"{today.isoformat()}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            tv = dt.date.fromisoformat(r["date"][:10])
            w.writerow({
                "capture_date": today.isoformat(),
                "travel_date": tv.isoformat(),
                "days_to_dep": (tv - today).days,
                "train_no": r["train_no"],
                "origine": r["origine"],
                "destination": r["destination"],
                "heure_depart": r.get("heure_depart"),
                "heure_arrivee": r.get("heure_arrivee"),
                "happy_card": 1 if r.get("od_happy_card") == "OUI" else 0,
            })
    print(f"{today}: {len(rows)} lignes -> {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
