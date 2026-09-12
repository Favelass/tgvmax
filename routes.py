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
    {"match": "STRASBOURG", "fetch": "STRASBOURG",              "buf": 15, "label": "Strasbourg", "short": "Strasbourg"},
    {"match": "MULHOUSE",   "fetch": "MULHOUSE VILLE",          "buf": 15, "label": "Mulhouse", "short": "Mulhouse"},
    {"match": "DIJON",      "fetch": "DIJON VILLE",             "buf": 15, "label": "Dijon", "short": "Dijon"},
    {"match": "BESANCON",   "fetch": "BESANCON - F COMTE TGV",  "buf": 15, "label": "Besançon", "short": "Besançon"},
    {"match": "BELFORT",    "fetch": "BELFORT-MONTBELIARD TGV", "buf": 15, "label": "Belfort", "short": "Belfort"},
    {"match": "intramuros", "fetch": "PARIS",                   "buf": 30, "label": "Paris (Est↔G.Lyon, M5)", "short": "Paris"},
]

# Backup retour Lyon -> CDG -> Lorraine TGV.
CDG_BACKUP = {"A": "LYON", "hub": "ROISSY", "B": "LORRAINE", "buf": 20, "label": "CDG", "short": "CDG"}

# Liaisons secondaires surveillées en direct (pas de correspondance).
WATCHLIST = [
    {"a": "LYON",         "b": "LILLE",      "na": "Lyon",         "nb": "Lille"},
    {"a": "intramuros",   "b": "HAZEBROUCK", "na": "Paris",        "nb": "Hazebrouck"},
    {"a": "LORRAINE TGV", "b": "LILLE",      "na": "Lorraine TGV", "nb": "Lille"},
]

# ── Cibles datées : alertes ponctuelles sur une OD + une date + un créneau ──
# Une cible = "préviens-moi dès qu'une place Max apparaît sur CETTE OD, CE
# jour-là, dans CE créneau de départ". Indépendant du diff Metz⇄Lyon : l'état
# est mémorisé dans data/targets_seen.json (1 alerte par train, pas de spam),
# et la cible s'éteint toute seule une fois la date passée.
#   o_match/d_match : matching dans les CSV (origine startswith / destination in)
#   fetch           : OD à récupérer côté collecteur
TARGETS = [
    {"date": "2026-10-04", "dep_min": "12:00", "dep_max": "19:00",
     "o_match": "PARIS", "d_match": "LYON (intra", "fetch": ("PARIS", "LYON"),
     "label": "Paris → Lyon (Part-Dieu/Perrache)", "note": ""},
    {"date": "2026-10-04", "dep_min": "12:00", "dep_max": "19:00",
     "o_match": "PARIS", "d_match": "LYON ST EXUPERY", "fetch": ("PARIS", "LYON"),
     "label": "Paris → Lyon St-Exupéry", "note": "aéroport : +Rhônexpress ~30 min / 16 €"},
    {"date": "2026-10-04", "dep_min": "12:00", "dep_max": "19:00",
     "o_match": "PARIS", "d_match": "ETIENNE", "fetch": ("PARIS", "ETIENNE"),
     "label": "Paris → Saint-Étienne", "note": "TGV direct (rare) ; sinon Lyon + TER hors TGVmax"},
]


def active_targets(today=None):
    """Cibles dont la date n'est pas passée (comparaison sur la date de voyage)."""
    import datetime as _dt
    today = today or _dt.date.today()
    return [t for t in TARGETS if _dt.date.fromisoformat(t["date"]) >= today]


# Seuils couleur (minutes) — pertinents pour les combos Metz<->Lyon.
DUREE_VERTE = 330   # <= 5h30 -> vert
DUREE_JAUNE = 420   # <= 7h00 -> jaune ; au-delà -> rouge
DIRECT_REF  = 290   # durée directe Metz<->Lyon de référence (4h50) si aucun direct ce jour-là


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
    for t in active_targets():
        pairs.append(tuple(t["fetch"]))
    seen, out = set(), []
    for p in pairs:
        if p not in seen:
            seen.add(p); out.append(p)
    return out
