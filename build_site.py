#!/usr/bin/env python3
"""Génère site/index.html : board statique des places Max du moment, à partir
de la dernière capture CSV. Réutilise la logique de alert.py (dédup incluse).
Déployé sur GitHub Pages par .github/workflows/pages.yml."""
import csv, glob, json, os
import datetime as dt
import alert

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")


def main():
    files = sorted(glob.glob(os.path.join(HERE, "data", "*T*Z.csv")))
    if not files:
        print("Aucune capture."); return
    rows = alert.load(files[-1])
    capture = rows[0]["capture_dt"] if rows else "?"
    allv = list(alert.build_journeys(rows).values())
    allv = alert.dedup(allv, allv)          # retire les combos dominés
    allv.sort(key=alert.order)

    data = []
    for j in allv:
        data.append({
            "pastille": alert.pastille(j),
            "route": j["route"] + (f" (via {j['short']})" if j["kind"] == "combo" else ""),
            "sens": j["sens"],
            "kind": j["kind"],
            "date": j["date"],
            "jour": alert.JOURS[dt.date.fromisoformat(j["date"]).weekday()],
            "dep": j["l1"]["heure_depart"],
            "arr": (j["l2"] if j["kind"] == "combo" else j["l1"])["heure_arrivee"],
            "dur": alert.hm(alert.total_min(j)),
            "lastminute": int(j["l1"]["days_to_dep"]) <= 2,
            "detail": (f"{j['l1']['heure_depart']}→{j['l1']['heure_arrivee']} ({j['l1']['train_no']}) → "
                       f"{j['l2']['heure_depart']}→{j['l2']['heure_arrivee']} ({j['l2']['train_no']}) "
                       f"· corresp {alert.hm(j['gap'])}{' ⚠️ serré' if j['gap'] <= j['buf'] + 10 else ''} via {j['hub']}"
                       if j["kind"] == "combo"
                       else f"train {j['l1']['train_no']}"),
        })

    os.makedirs(SITE, exist_ok=True)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
                    .replace("__CAPTURE__", capture)
                    .replace("__N__", str(len(data))))
    print(f"site/index.html généré : {len(data)} trajets (capture {capture})")


HTML = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TGVmax — places du moment</title>
<style>
:root{--bg:#0f1216;--card:#171b21;--bd:#262c35;--tx:#e6e9ee;--mut:#8b95a3;--ac:#3b82f6}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--tx)}
header{padding:20px 16px;border-bottom:1px solid var(--bd)}
h1{margin:0 0 4px;font-size:19px}.sub{color:var(--mut);font-size:13px}
.filters{display:flex;flex-wrap:wrap;gap:8px;padding:14px 16px;position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--bd);z-index:2}
.filters button{background:var(--card);color:var(--tx);border:1px solid var(--bd);border-radius:20px;padding:6px 14px;cursor:pointer;font-size:13px}
.filters button.on{background:var(--ac);border-color:var(--ac);color:#fff}
main{padding:8px 12px 40px;max-width:760px;margin:0 auto}
.day{margin:18px 0 6px;font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.j{display:flex;gap:10px;align-items:flex-start;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:10px 12px;margin:6px 0}
.j .p{font-size:16px;line-height:1.4}
.j .m{flex:1;min-width:0}
.j .r{font-weight:600}.j .lm{color:#f59e0b;font-weight:600}
.j .t{color:var(--mut);font-size:13px;margin-top:2px}
.dur{white-space:nowrap;color:var(--mut);font-size:13px}
.empty{color:var(--mut);text-align:center;padding:40px}
</style></head><body>
<header><h1>🎫 TGVmax — places du moment</h1>
<div class="sub">__N__ trajets · capture __CAPTURE__ · l'opendata SNCF est mise à jour 1×/jour</div></header>
<div class="filters" id="f"></div>
<main id="list"></main>
<script>
const DATA=__DATA__;
const GROUPS=[["Tous",()=>1],["Metz⇄Lyon",j=>j.sens=="aller"||j.sens=="retour"],
["💎 bat le direct",j=>j.pastille=="💎"],["⚡ <48h",j=>j.lastminute],["Secondaires",j=>j.sens!="aller"&&j.sens!="retour"]];
let cur=0;
const fbox=document.getElementById("f");
GROUPS.forEach((g,i)=>{const b=document.createElement("button");b.textContent=g[0];
b.className=i==0?"on":"";b.onclick=()=>{cur=i;[...fbox.children].forEach(c=>c.classList.remove("on"));b.classList.add("on");render()};fbox.appendChild(b)});
function render(){
 const list=document.getElementById("list");list.innerHTML="";
 const items=DATA.filter(GROUPS[cur][1]);
 if(!items.length){list.innerHTML='<div class="empty">Aucun trajet.</div>';return}
 let lastDate="";
 for(const j of items){
  if(j.date!=lastDate){lastDate=j.date;const d=document.createElement("div");
   d.className="day";d.textContent=j.jour+" "+j.date.split("-").reverse().join("/");list.appendChild(d)}
  const el=document.createElement("div");el.className="j";
  el.innerHTML=`<div class="p">${j.pastille}</div><div class="m">
   <div class="r">${j.lastminute?'<span class="lm">⚡ </span>':''}${j.route}</div>
   <div class="t">${j.dep}→${j.arr} · ${j.detail}</div></div>
   <div class="dur">${j.dur}</div>`;
  list.appendChild(el);
 }
}
render();
</script></body></html>"""


if __name__ == "__main__":
    main()
