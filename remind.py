#!/usr/bin/env python3
"""Rappel quotidien 17h15 : checker le dernière-minute (<48h) à la main sur
l'app/SNCF Connect, pendant la vague de remises en vente post-confirmation.
Aucun scraping — juste une notification de notre propre bot.
Secrets : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID."""
import os, json, urllib.parse, urllib.request

MSG = ("🔔 17h15 — fenêtre dernière-minute\n\n"
       "Les places Max <48h non confirmées se libèrent maintenant.\n"
       "Check à la main : app SNCF / « Il reste des places à bord » Metz⇄Lyon.\n"
       "(l'opendata ne voit pas l'intraday, d'où ce rappel)")


def main():
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("Secrets absents -> pas d'envoi.\n" + MSG); return
    data = urllib.parse.urlencode({"chat_id": chat, "text": MSG,
                                   "disable_web_page_preview": "true"}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=20))
    print("Rappel envoyé." if r.get("ok") else r)


if __name__ == "__main__":
    main()
