#!/usr/bin/env python3
"""Alerte Telegram : diff des 2 dernières captures -> notifie les trajets Max
qui viennent d'apparaître. Config des liaisons dans routes.py.
Secrets : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Absents -> pas d'envoi, exit 0."""
import csv, glob, json, os, urllib.parse, urllib.request
import datetime as dt
import routes

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
JOURS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
MAX_LAYOVER = 240


def passe_filtre(j):
    return True
    # wd = dt.date.fromisoformat(j["date"]).weekday()
    # if j["sens"] == "aller"  and wd not in (3, 4): return False
    # if j["sens"] == "retour" and wd != 6:          return False


def mins(hhmm):
    h, m = hhmm.split(":"); return int(h) * 60 + int(m)


def hm(m):
    return f"{m // 60}h{m % 60:02d}"


def load(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seg(rows, a, b):
    out = {}
    for r in rows:
        if r["happy_card"] == "1" and a in r["origine"] and b in r["destination"]:
            out.setdefault(r["travel_date"], []).append(r)
    return out


def build_journeys(rows):
    J = {}

    def add_direct(sens, route, A, B):
        for date, rs in seg(rows, A, B).items():
            for r in rs:
                J[(date, sens, "D", r["train_no"])] = {
                    "sens": sens, "route": route, "date": date, "kind": "direct", "l1": r}

    def add_via(sens, route, A, hub, B, buf, lbl):
        l1s, l2s = seg(rows, A, hub), seg(rows, hub, B)
        for date in l1s.keys() & l2s.keys():
            for r1 in l1s[date]:
                for r2 in l2s[date]:
                    gap = mins(r2["heure_depart"]) - mins(r1["heure_arrivee"])
                    if buf <= gap <= MAX_LAYOVER:
                        J[(date, sens, "C", hub, r1["train_no"], r2["train_no"])] = {
                            "sens": sens, "route": route, "date": date, "kind": "combo",
                            "l1": r1, "l2": r2, "gap": gap, "hub": lbl}

    add_direct("aller", "Metz→Lyon", routes.METZ_MATCH, routes.LYON)
    add_direct("retour", "Lyon→Metz", routes.LYON, routes.METZ_MATCH)
    for h in routes.HUBS:
        add_via("aller", "Metz→Lyon", routes.METZ_MATCH, h["match"], routes.LYON, h["buf"], h["label"])
        add_via("retour", "Lyon→Metz", routes.LYON, h["match"], routes.METZ_MATCH, h["buf"], h["label"])
    c = routes.CDG_BACKUP
    add_via("retour", "Lyon→Lorraine TGV", c["A"], c["hub"], c["B"], c["buf"], c["label"])
    for w in routes.WATCHLIST:
        add_direct(f"{w['na']}→{w['nb']}", f"{w['na']}→{w['nb']}", w["a"], w["b"])
        add_direct(f"{w['nb']}→{w['na']}", f"{w['nb']}→{w['na']}", w["b"], w["a"])
    return J


def jdep(j):
    return mins(j["l1"]["heure_depart"])


def jarr(j):
    return mins((j["l2"] if j["kind"] == "combo" else j["l1"])["heure_arrivee"])


def total_min(j):
    return jarr(j) - jdep(j)


def pastille(j):
    # Couleur seulement pour les combos Metz<->Lyon (là où la durée varie).
    if j["kind"] != "combo" or j["route"] not in ("Metz→Lyon", "Lyon→Metz"):
        return "🚆"
    t = total_min(j)
    return "🟢" if t <= routes.DUREE_VERTE else ("🟡" if t <= routes.DUREE_JAUNE else "🔴")


def dedup(cur_journeys, candidates):
    """Retire un combo s'il est dominé (même sens+date, un autre trajet part
    aussi tard/plus tard ET arrive aussi tôt/plus tôt, strictement meilleur)."""
    out = []
    for j in candidates:
        if j["kind"] != "combo":
            out.append(j); continue
        dominated = False
        for o in cur_journeys:
            if o is j or o["sens"] != j["sens"] or o["date"] != j["date"]:
                continue
            if jdep(o) >= jdep(j) and jarr(o) <= jarr(j) and \
               (jdep(o) > jdep(j) or jarr(o) < jarr(j)):
                dominated = True; break
        if not dominated:
            out.append(j)
    return out


def fmt(j):
    wd = JOURS[dt.date.fromisoformat(j["date"]).weekday()]
    jj = "/".join(reversed(j["date"].split("-")[1:]))
    lm = "⚡ " if int(j["l1"]["days_to_dep"]) <= 2 else ""
    tot = hm(total_min(j))
    if j["kind"] == "direct":
        r = j["l1"]
        return (f"{pastille(j)} {lm}{j['route']} · {wd} {jj}\n"
                f"   {r['heure_depart']}→{r['heure_arrivee']} · {tot} · train {r['train_no']}")
    r1, r2 = j["l1"], j["l2"]
    return (f"{pastille(j)} {lm}{j['route']} via {j['hub']} · {wd} {jj}\n"
            f"   {r1['heure_depart']}→{r1['heure_arrivee']} ({r1['train_no']}) → "
            f"{r2['heure_depart']}→{r2['heure_arrivee']} ({r2['train_no']})\n"
            f"   ⏱ {tot} · corresp {hm(j['gap'])}")


def send(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("Secrets Telegram absents -> pas d'envoi.\n" + text); return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=20) as r:
        json.load(r)
    print("Telegram envoye.")


def order(j):
    return (int(j["l1"]["days_to_dep"]), total_min(j), j["sens"], j["l1"]["heure_depart"])


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*T*Z.csv")))
    if len(files) < 2:
        print("Moins de 2 captures -> pas de diff (1er run)."); return
    prev, cur = build_journeys(load(files[-2])), build_journeys(load(files[-1]))
    news = [cur[k] for k in cur.keys() - prev.keys() if passe_filtre(cur[k])]
    news = sorted(dedup(list(cur.values()), news), key=order)
    if not news:
        print("Aucun nouveau trajet Max."); return
    blocs = "\n\n".join(fmt(j) for j in news[:25])
    extra = f"\n\n… +{len(news) - 25} autres" if len(news) > 25 else ""
    text = (f"🎫 {len(news)} nouveau(x) trajet(s) Max\n"
            f"🟢<5h30 🟡<7h 🔴+ (combos) · ⚡ = <48h\n\n{blocs}{extra}\n\n"
            f"→ réserver : https://www.sncf-connect.com/")
    send(text)


if __name__ == "__main__":
    main()
