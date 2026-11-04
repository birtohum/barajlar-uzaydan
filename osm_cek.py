"""OSM'den (Overpass) İstanbul su yüzeyi poligonlarını çeker. Tek seferlik; sonuç veri/ altında saklanır."""
import json, sys, time, requests

AYNALAR = ["https://overpass-api.de/api/interpreter",
           "https://overpass.private.coffee/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]
UA = {"User-Agent": "barajlar-uzaydan/0.1 (+https://github.com/birtohum/barajlar-uzaydan)"}

def sorgula(q):
    bekle = 5
    for tur in range(6):
        for u in AYNALAR:
            try:
                r = requests.post(u, data={"data": q}, headers=UA, timeout=200)
                if r.ok and r.text.lstrip().startswith("{"):
                    return r.json()
                print(u, r.status_code, r.text[:80].replace("\n", " "), file=sys.stderr)
            except Exception as e:
                print(u, e, file=sys.stderr)
        time.sleep(bekle); bekle *= 2
    raise SystemExit("Overpass yanıt vermedi")

if __name__ == "__main__":
    q = sys.argv[1]; cikti = sys.argv[2]
    d = sorgula(q)
    json.dump(d, open(cikti, "w", encoding="utf8"), ensure_ascii=False)
    print(len(d["elements"]), "öğe")
