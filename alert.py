#!/usr/bin/env python3
"""Alerte Telegram : diff des 2 dernières captures -> notifie les trajets Max
qui viennent d'apparaître. Config des liaisons dans routes.py.
Secrets : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Absents -> pas d'envoi, exit 0."""
import csv, glob, json, os, urllib.parse, urllib.request
import datetime as dt
import routes

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATE_TARGETS = os.path.join(DATA_DIR, "targets_seen.json")
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

    def add_via(sens, route, A, hub, B, buf, lbl, short):
        l1s, l2s = seg(rows, A, hub), seg(rows, hub, B)
        for date in l1s.keys() & l2s.keys():
            for r1 in l1s[date]:
                for r2 in l2s[date]:
                    gap = mins(r2["heure_depart"]) - mins(r1["heure_arrivee"])
                    if buf <= gap <= MAX_LAYOVER:
                        J[(date, sens, "C", hub, r1["train_no"], r2["train_no"])] = {
                            "sens": sens, "route": route, "date": date, "kind": "combo",
                            "l1": r1, "l2": r2, "gap": gap, "hub": lbl, "short": short, "buf": buf}

    add_direct("aller", "Metz→Lyon", routes.METZ_MATCH, routes.LYON)
    add_direct("retour", "Lyon→Metz", routes.LYON, routes.METZ_MATCH)
    for h in routes.HUBS:
        add_via("aller", "Metz→Lyon", routes.METZ_MATCH, h["match"], routes.LYON, h["buf"], h["label"], h["short"])
        add_via("retour", "Lyon→Metz", routes.LYON, h["match"], routes.METZ_MATCH, h["buf"], h["label"], h["short"])
    c = routes.CDG_BACKUP
    add_via("retour", "Lyon→Lorraine TGV", c["A"], c["hub"], c["B"], c["buf"], c["label"], c["short"])
    for w in routes.WATCHLIST:
        add_direct(f"{w['na']}→{w['nb']}", f"{w['na']}→{w['nb']}", w["a"], w["b"])
        add_direct(f"{w['nb']}→{w['na']}", f"{w['nb']}→{w['na']}", w["b"], w["a"])
    _annotate_beats_direct(J)
    return J


ML = ("Metz→Lyon", "Lyon→Metz")


def _annotate_beats_direct(J):
    """Marque les combos Metz<->Lyon plus rapides que le direct du jour (ou que
    DIRECT_REF si aucun direct)."""
    best = {}
    for j in J.values():
        if j["kind"] == "direct" and j["route"] in ML:
            k = (j["sens"], j["date"])
            best[k] = min(best.get(k, 10 ** 9), total_min(j))
    for j in J.values():
        if j["kind"] == "combo" and j["route"] in ML:
            ref = best.get((j["sens"], j["date"]), routes.DIRECT_REF)
            j["beats_direct"] = total_min(j) < ref


def jdep(j):
    return mins(j["l1"]["heure_depart"])


def jarr(j):
    return mins((j["l2"] if j["kind"] == "combo" else j["l1"])["heure_arrivee"])


def total_min(j):
    return jarr(j) - jdep(j)


def pastille(j):
    # Neutre pour directs et secondaires.
    if j["kind"] != "combo" or j["route"] not in ML:
        return "🚆"
    if j.get("beats_direct"):          # combo plus rapide que le direct
        return "💎"
    t = total_min(j)
    return "🟢" if t <= routes.DUREE_VERTE else ("🟡" if t <= routes.DUREE_JAUNE else "🔴")


def dedup(cur_journeys, candidates):
    """Retire un combo s'il est dominé (même sens+date, un autre trajet part
    aussi tard/plus tard ET arrive aussi tôt/plus tôt, strictement meilleur)."""
    out, seen = [], set()
    for j in candidates:
        if j["kind"] != "combo":
            out.append(j); continue
        sig = (j["sens"], j["date"], jdep(j), jarr(j))
        if sig in seen:            # meme sens/date/horaires -> un seul
            continue
        dominated = False
        for o in cur_journeys:
            if o is j or o["sens"] != j["sens"] or o["date"] != j["date"]:
                continue
            if jdep(o) >= jdep(j) and jarr(o) <= jarr(j) and \
               (jdep(o) > jdep(j) or jarr(o) < jarr(j)):
                dominated = True; break
        if not dominated:
            seen.add(sig); out.append(j)
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
    return (f"{pastille(j)} {lm}{j['route']} (via {j['short']}) · {wd} {jj}\n"
            f"   {r1['heure_depart']}→{r1['heure_arrivee']} ({r1['train_no']}) → "
            f"{r2['heure_depart']}→{r2['heure_arrivee']} ({r2['train_no']})\n"
            f"   ⏱ {tot} · corresp {hm(j['gap'])}{' ⚠️ serré' if j['gap'] <= j['buf'] + 10 else ''} · {j['hub']}")


# ── Cibles datées (routes.TARGETS) ────────────────────────────────────────
# Logique volontairement séparée du diff Metz⇄Lyon : ici on ne veut pas rater
# une place parce qu'elle était déjà là à la capture précédente. On mémorise
# donc les trains déjà notifiés dans data/targets_seen.json (committé par le
# workflow) -> 1 alerte par train, même au 1er run après déploiement.

def target_hits(rows, today=None):
    """Places Max correspondant à une cible active. Dédoublonné par
    (date, train, heure de départ, destination) — un même train apparaît 2x
    dans l'opendata (Part-Dieu puis Perrache) : on garde l'arrivée la plus tôt."""
    best = {}
    for t in routes.active_targets(today):
        for r in rows:
            if (r["happy_card"] == "1"
                    and r["travel_date"] == t["date"]
                    and r["origine"].startswith(t["o_match"])
                    and t["d_match"] in r["destination"]
                    and t["dep_min"] <= r["heure_depart"] <= t["dep_max"]):
                sig = f"{t['date']}|{t['d_match']}|{r['train_no']}|{r['heure_depart']}"
                cur = best.get(sig)
                if cur is None or r["heure_arrivee"] < cur["r"]["heure_arrivee"]:
                    best[sig] = {"sig": sig, "t": t, "r": r}
    return sorted(best.values(), key=lambda h: (h["r"]["travel_date"], h["r"]["heure_depart"]))


def load_seen():
    try:
        with open(STATE_TARGETS, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_seen(sigs):
    with open(STATE_TARGETS, "w", encoding="utf-8") as f:
        json.dump(sorted(sigs), f, ensure_ascii=False, indent=0)


def fmt_target(h):
    t, r = h["t"], h["r"]
    wd = JOURS[dt.date.fromisoformat(r["travel_date"]).weekday()]
    jj = "/".join(reversed(r["travel_date"].split("-")[1:]))
    dur = hm(mins(r["heure_arrivee"]) - mins(r["heure_depart"]))
    note = f"\n   ⚠️ {t['note']}" if t["note"] else ""
    return (f"🔥 {t['label']} · {wd} {jj}\n"
            f"   {r['heure_depart']}→{r['heure_arrivee']} · {dur} · train {r['train_no']}{note}")


def alert_targets(rows, today=None):
    """Notifie les places Max sur cibles jamais encore signalées. True si envoi."""
    actives = routes.active_targets(today)
    if not actives:
        return False
    hits = target_hits(rows, today)
    seen = load_seen()
    news = [h for h in hits if h["sig"] not in seen]
    if news:
        creneaux = ", ".join(sorted({f"{t['dep_min']}–{t['dep_max']}" for t in actives}))
        # send() AVANT save_seen() : si Telegram tombe, l'état n'est pas écrit
        # et la place est renotifiée au run suivant (mieux que la perdre).
        send(f"🎯 CIBLE — {len(news)} place(s) Max sur ta demande ({creneaux})\n\n"
             + "\n\n".join(fmt_target(h) for h in news)
             + "\n\n⏳ ça part en minutes → réserve tout de suite : "
               "https://www.sncf-connect.com/")
    else:
        print(f"Cibles : {len(hits)} place(s) Max, rien de nouveau.")
    # Purge des signatures dont la cible a expiré ; on garde celles encore suivies.
    save_seen({h["sig"] for h in hits} |
              {s for s in seen if any(s.startswith(t["date"]) for t in actives)})
    return bool(news)


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
    if not files:
        print("Aucune capture."); return
    if len(files) < 2:
        alert_targets(load(files[-1]))
        print("Moins de 2 captures -> pas de diff (1er run)."); return
    last_rows = load(files[-1])
    alert_targets(last_rows)
    prev, cur = build_journeys(load(files[-2])), build_journeys(last_rows)
    news = [cur[k] for k in cur.keys() - prev.keys() if passe_filtre(cur[k])]
    news = sorted(dedup(list(cur.values()), news), key=order)
    if not news:
        print("Aucun nouveau trajet Max."); return
    blocs = "\n\n".join(fmt(j) for j in news[:25])
    extra = f"\n\n… +{len(news) - 25} autres" if len(news) > 25 else ""
    text = (f"🎫 {len(news)} nouveau(x) trajet(s) Max\n"
            f"💎 bat le direct · 🟢<5h30 🟡<7h 🔴+ · ⚡ <48h\n\n{blocs}{extra}\n\n"
            f"→ réserver : https://www.sncf-connect.com/")
    send(text)


if __name__ == "__main__":
    main()
