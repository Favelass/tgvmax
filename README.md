# tgvmax-metz-paris

Historisation quotidienne de la disponibilité TGVmax sur l'axe **Metz ⇄ Paris**.

## Pourquoi

Le [dataset SNCF `tgvmax`](https://data.sncf.com/explore/dataset/tgvmax/) est une
photo glissante J..J+30, **écrasée chaque matin, sans aucun historique**. Impossible
d'y voir comment la dispo d'un train évolue à l'approche du départ.

Ce repo comble le trou : un run quotidien capture l'état courant et l'archive,
horodaté. En accumulant, on reconstruit la courbe *dispo vs jours-avant-départ*
par train × date — la seule base exploitable pour décider quand réserver.

## Contenu

- `collect_tgvmax_metz_paris.py` — collecteur (stdlib seule, aucune dépendance).
- `.github/workflows/collect.yml` — run quotidien (08:00 UTC) + commit auto des CSV.
- `data/AAAA-MM-JJ.csv` — une capture par jour.

## Schéma CSV

`capture_date, travel_date, days_to_dep, train_no, origine, destination, heure_depart, heure_arrivee, happy_card`

`happy_card` : 1 = place Max réservable à l'instant de la capture, 0 = non.

## Limites (à lire)

- Historique = **à partir du 1er run**. Aucune donnée antérieure n'existe nulle part.
- Chaque jour non collecté est perdu définitivement.
- `days_to_dep` va de 0 à ~30 ; un voyage n'a une courbe complète que si la collecte
  a démarré ≥30 j avant sa date.
