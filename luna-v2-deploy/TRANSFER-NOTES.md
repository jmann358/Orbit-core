# TRANSFER NOTES (THRONE install, Codex: read me first)

The seed database travels as a TEXT SQL dump (binary .db could not ride
this transfer channel as raw bytes):

    sqlite3 luna_v2.db < luna_v2_seed.sql

That dump is verified: it loads clean into a fresh SQLite file and
yields 6 missions / 6 receipts, identical to the live seed. After the
load, spot-check with:

    sqlite3 luna_v2.db "select count(*) from missions;"

expect 6. This luna_v2.db becomes THRONE's live database — the Mac's
copy is canonical from install on.

The three PWA icons (luna_v2/assets/*.png) ARE included below as
base64 text; decode them:

    base64 -d luna_v2/assets/icon-192.png.b64 > luna_v2/assets/icon-192.png
    base64 -d luna_v2/assets/icon-512.png.b64 > luna_v2/assets/icon-512.png
    base64 -d luna_v2/assets/apple-touch-icon.png.b64 > luna_v2/assets/apple-touch-icon.png
