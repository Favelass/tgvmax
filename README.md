# tgvmax-metz-paris

Suivi quotidien de la disponibilité TGVmax sur **Metz⇄Paris**, **Metz⇄Lyon** et **Paris⇄Lyon**,
avec **alerte Telegram** à chaque nouvelle place Max Metz⇄Lyon,
et **alertes ciblées** sur une date + un créneau précis (`TARGETS`).

## Pourquoi
Le dataset SNCF `tgvmax` est une photo glissante J..J+30, écrasée chaque jour,
sans historique. Ce repo capture l'état plusieurs fois/jour, l'archive horodaté,
et notifie les nouveautés.

## Config
Toutes les liaisons (hubs, backup CDG, watchlist, seuils couleur) sont dans
**`routes.py`** — seul fichier à éditer pour ajouter/retirer une liaison.

## Pièces
- `collect_tgvmax_metz_paris.py` — collecteur multi-lignes (stdlib seule).
- `alert.py` — diff des 2 dernières captures + push Telegram. Détecte les trajets Max
  **Metz⇄Lyon** directs et correspondances (Strasbourg, Mulhouse, Dijon, Besançon,
  Belfort, Paris) + un **backup retour Lyon→CDG→Lorraine TGV** (finir en navette). (2 billets séparés, battements réalistes (~15 min même gare, 60 min Paris Est↔G.Lyon),
  dédoublonnage par trains, réglable en tête de `alert.py`).
- `.github/workflows/collect.yml` — runs 06h30 & 14h30 Paris + commit auto.
- `data/<datetime>Z.csv` — une capture horodatée par run.

## Configurer les alertes Telegram
1. Sur Telegram, parle à `@BotFather` → `/newbot` → récupère le **token**.
2. Écris un message à ton bot, puis ouvre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → récupère ton **chat id**.
3. Repo GitHub → Settings → Secrets and variables → Actions → New secret :
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

Sans ces secrets, le workflow tourne quand même mais n'envoie rien.

## Affiner les critères
Dans `alert.py`, fonction `passe_criteres` : décommente pour filtrer par jour
(aller jeu/ven, retour dim) ou heure mini. Par défaut : toutes les places Max
Metz⇄Lyon (le Max Lyon est rare, mieux vaut tout voir). Le combo via Paris double/triple
les options, mais reste limité par le segment Metz⇄Paris (Max rare aussi).
Lyon⇄St-Étienne = TER, hors TGVmax (non modélisé) ; en revanche **Paris⇄St-Étienne**
a des TGV inOui directs, éligibles Max : voir les cibles datées ci-dessous.

## Alertes ciblées (une date, un créneau)
Pour un besoin ponctuel — « préviens-moi s'il y a un Paris→Lyon le dim 4 oct
après-midi » — on ajoute une entrée dans **`TARGETS`** (`routes.py`) :
OD + date + fenêtre de départ. Le collecteur récupère l'OD automatiquement,
`alert.py` envoie une alerte 🎯 dès qu'une place Max y apparaît, et la cible
s'éteint seule une fois la date passée.

Différence avec l'alerte principale : pas de diff entre 2 captures (on raterait
une place déjà présente au 1er run) mais un **état** dans
`data/targets_seen.json` → **1 alerte par train**, jamais de spam.
À J-3 le rappel 17h15 (`remind.py`) rappelle la cible : à ce stade les remises
en vente passent par l'intraday, que l'opendata ne voit pas.

Observé sur les dimanches Paris→Lyon : en été les places sortaient surtout à
J-3..J-0, mais depuis la rentrée elles n'apparaissent qu'entre **J-25 et J-10**
et sont épuisées bien avant le départ. Une cible se joue donc tôt, pas la veille.

**Limite dure** : l'opendata SNCF n'est rafraîchie qu'**1×/jour** (vérifié :
sur 10 jours, les captures 07h et 15h sont strictement identiques). Une place
prise dans la journée n'apparaîtra jamais. Poller plus souvent n'y changerait
rien — le dernière-minute se joue à la main sur l'app.

## Hors périmètre (volontairement)
Pas de réservation automatique : SNCF Connect bloque les bots, et aucun agent
ne peut être convoqué à heure fixe pour piloter un navigateur. La réservation
reste manuelle (1 tap depuis l'alerte). Assistance navigateur possible plus tard,
en session interactive uniquement.

## Liaisons secondaires surveillées
En plus de Metz⇄Lyon, alerte sur les directs Max de : Lyon⇄Lille,
Paris⇄Hazebrouck, Lorraine TGV⇄Lille. Modifiable via `WATCHLIST` dans `alert.py`
(et `ROUTES` dans le collecteur). Ces liaisons sont suivies en **direct only**
(pas de correspondances).

## Board web (GitHub Pages)
`build_site.py` génère `site/index.html` (places Max du moment, filtrable) à
partir de la dernière capture. Déployé par `.github/workflows/pages.yml` après
chaque collecte. **À activer une fois** : repo → Settings → Pages → Source =
**GitHub Actions**. C'est un outil de consultation (pull), complément des alertes.
