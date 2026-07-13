"""Config centrale des liaisons — SOURCE DE VÉRITÉ unique.
Importée par le collecteur (quelles OD récupérer) ET l'alerteur (comment les
assembler et les afficher). Ajouter une liaison = éditer ICI seulement.

Champs des hubs :
  match : sous-chaîne pour reconnaître la gare dans les CSV (matching alerteur)
  fetch : token pour la requête opendata ODS LIKE (collecteur)
  buf   : battement mini de correspondance (minutes)
  label : libellé d'affichage
"""

METZ_FETCH = "METZ VILLE"   # exact côté collecteur
METZ_MATCH = "METZ"         # sous-chaîne côté alerteur
LYON = "LYON"

# Hubs de correspondance Metz<->Lyon.
HUBS = [
    {"match": "STRASBOURG", "fetch": "STRASBOURG",              "buf": 15, "label": "Strasbourg"},
    {"match": "MULHOUSE",   "fetch": "MULHOUSE VILLE",          "buf": 15, "label": "Mulhouse"},
    {"match": "DIJON",      "fetch": "DIJON VILLE",             "buf": 15, "label": "Dijon"},
    {"match": "BESANCON",   "fetch": "BESANCON - F COMTE TGV",  "buf": 15, "label": "Besançon"},
    {"match": "BELFORT",    "fetch": "BELFORT-MONTBELIARD TGV", "buf": 15, "label": "Belfort"},
    {"match": "intramuros", "fetch": "PARIS",                   "buf": 30, "label": "Paris (Est↔G.Lyon, M5)"},
]

# Backup retour Lyon -> CDG -> Lorraine TGV.
CDG_BACKUP = {"A": "LYON", "hub": "ROISSY", "B": "LORRAINE", "buf": 20, "label": "CDG"}

# Liaisons secondaires surveillées en direct (pas de correspondance).
WATCHLIST = [
    {"a": "LYON",         "b": "LILLE",      "na": "Lyon",         "nb": "Lille"},
    {"a": "intramuros",   "b": "HAZEBROUCK", "na": "Paris",        "nb": "Hazebrouck"},
    {"a": "LORRAINE TGV", "b": "LILLE",      "na": "Lorraine TGV", "nb": "Lille"},
]

# Seuils couleur (minutes) — pertinents pour les combos Metz<->Lyon.
DUREE_VERTE = 330   # <= 5h30 -> vert
DUREE_JAUNE = 420   # <= 7h00 -> jaune ; au-delà -> rouge


def _fetch(tok):
    return "PARIS" if tok == "intramuros" else tok


def collect_pairs():
    """Toutes les OD à récupérer par le collecteur (les 2 sens sont ajoutés
    automatiquement par build_where). Dédoublonnées."""
    pairs = [(METZ_FETCH, LYON)]
    for h in HUBS:
        pairs += [(METZ_FETCH, h["fetch"]), (h["fetch"], LYON)]
    pairs += [("LYON", "ROISSY"), ("ROISSY", "LORRAINE TGV")]
    for w in WATCHLIST:
        pairs.append((_fetch(w["a"]), _fetch(w["b"])))
    seen, out = set(), []
    for p in pairs:
        if p not in seen:
            seen.add(p); out.append(p)
    return out
