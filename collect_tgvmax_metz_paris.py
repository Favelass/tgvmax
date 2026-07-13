#!/usr/bin/env python3
"""Collecteur TGVmax. Capture l'état courant J..J+30, horodaté à la minute ->
data/<datetime>Z.csv. Les OD à récupérer viennent de routes.collect_pairs()."""
import csv, datetime as dt, json, os, sys, urllib.parse, urllib.request
import routes

BASE = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/records"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ROUTES = routes.collect_pairs()
FIELDS = ["capture_dt", "capture_date", "travel_date", "days_to_dep",
          "train_no", "origine", "destination", "heure_depart",
          "heure_arrivee", "happy_card"]


def _clause(field, token):
    return f'{field}="{token}"' if token == "METZ VILLE" else f'{field} LIKE "{token}"'


def build_where():
    parts = []
    for a, b in ROUTES:
        parts.append(f'({_clause("origine", a)} AND {_clause("destination", b)})')
        parts.append(f'({_clause("origine", b)} AND {_clause("destination", a)})')
    return " OR ".join(parts)


def fetch_all(where):
    rows, offset, limit = [], 0, 100
    while True:
        qs = urllib.parse.urlencode({"where": where, "limit": limit,
                                     "offset": offset, "order_by": "date,heure_depart"})
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
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    rows = fetch_all(build_where())
    if not rows:
        print("AUCUNE donnee - filtre/API a verifier", file=sys.stderr); sys.exit(1)
    os.makedirs(DATA_DIR, exist_ok=True)
    stamp = now.strftime("%Y-%m-%dT%H%MZ")
    out = os.path.join(DATA_DIR, f"{stamp}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in rows:
            tv = dt.date.fromisoformat(r["date"][:10])
            w.writerow({"capture_dt": now.isoformat(timespec="minutes"),
                        "capture_date": today.isoformat(), "travel_date": tv.isoformat(),
                        "days_to_dep": (tv - today).days, "train_no": r["train_no"],
                        "origine": r["origine"], "destination": r["destination"],
                        "heure_depart": r.get("heure_depart"), "heure_arrivee": r.get("heure_arrivee"),
                        "happy_card": 1 if r.get("od_happy_card") == "OUI" else 0})
    n_oui = sum(1 for r in rows if r.get("od_happy_card") == "OUI")
    print(f"{stamp}: {len(rows)} lignes ({n_oui} Max) -> {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
