"""Sentinel-2 L2A arşivinden (AWS açık veri, Element84 Earth Search STAC) baraj su yüzeyi ölçer.

Kullanım:
  python cek.py                 # 2017'den bugüne, eksik olan her görüntüyü işler
  python cek.py --gun 30        # yalnız son 30 günü tarar (günlük güncelleme)

Sonuç: veri/olcumler.csv (her baraj x her görüntü bir satır; bulutlu olanlar da gecerli=0 ile tutulur,
böylece aynı görüntü tekrar indirilmez).
"""
import argparse, csv, datetime as dt, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")

import numpy as np
import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

from barajlar import BARAJLAR
from olcum import alan_hesapla, yansitim
from poligon import utm

STAC = "https://earth-search.aws.element84.com/v1/search"
KOLEKSIYON = "sentinel-2-l2a"
BASLANGIC = "2017-01-01"
TAMPON_M = 30          # OSM çizgisinin biraz dışına taşan suyu da yakalamak için
ENFAZLA_KARE_BULUT = 90
CSV = "veri/olcumler.csv"
ALANLAR = ["kod", "tarih", "goruntu", "alan_km2", "ham_alan_km2", "gorunmez_oran", "gecerli", "su_piksel", "cerceve_piksel"]


def cerceveler():
    fc = json.load(open("veri/barajlar.geojson", encoding="utf8"))
    g = {f["properties"]["kod"]: utm(shape(f["geometry"])) for f in fc["features"]}
    sonuc = {}
    for b in BARAJLAR:
        alan = g[b["kod"]].buffer(TAMPON_M)
        x0, y0, x1, y1 = alan.bounds
        # 20 m ızgaraya dışa doğru yasla: 10 m ve 20 m pencereler birebir örtüşsün
        x0 = np.floor(x0 / 20) * 20 - 20; y0 = np.floor(y0 / 20) * 20 - 20
        x1 = np.ceil(x1 / 20) * 20 + 20; y1 = np.ceil(y1 / 20) * 20 + 20
        sonuc[b["kod"]] = {"geom": alan, "sinir": (x0, y0, x1, y1), "kare": b["kare"]}
    return sonuc


def ara(kare, bas, son):
    """STAC araması; uzun aralıklar sunucuda zaman aşımına düştüğü için çeyrek yıllık parçalara böler."""
    b = dt.date.fromisoformat(bas); s = dt.date.fromisoformat(son)
    ogeler = []
    while b <= s:
        p = min(s, b + dt.timedelta(days=91))
        ogeler += _ara(kare, b.isoformat(), p.isoformat())
        b = p + dt.timedelta(days=1)
    # aynı gün yeniden işlenmiş kopyalar (_0, _1): en yüksek sıra numarasını tut
    gun = {}
    for f in ogeler:
        t = f["properties"]["datetime"][:10]
        n = int(f["properties"].get("s2:sequence", 0) or 0)
        if t not in gun or n > gun[t][0]:
            gun[t] = (n, f)
    return [v[1] for k, v in sorted(gun.items())]


def _ara(kare, bas, son):
    govde = {"collections": [KOLEKSIYON], "query": {"grid:code": {"eq": "MGRS-" + kare},
             "eo:cloud_cover": {"lte": ENFAZLA_KARE_BULUT}},
             "datetime": f"{bas}T00:00:00Z/{son}T23:59:59Z", "limit": 100}
    ogeler = []
    while True:
        for deneme in range(8):
            try:
                r = requests.post(STAC, json=govde, timeout=120); r.raise_for_status(); break
            except Exception as e:
                print("STAC hata, yeniden:", e, file=sys.stderr); time.sleep(5 * (deneme + 1))
        else:
            raise SystemExit("STAC yanıt vermiyor")
        d = r.json(); ogeler += d["features"]
        sonraki = [l for l in d.get("links", []) if l["rel"] == "next"]
        if not sonraki:
            break
        govde = sonraki[0].get("body", govde)
    return ogeler


def bant(oge, ad):
    """Bandın adresi, ölçeği ve ötelemesi.

    2022'den beri (işleme sürümü 04.00+) ESA ham değerlere +1000 ekliyor. Earth Search bu
    kaydırmayı COG'larda zaten geri almışsa (earthsearch:boa_offset_applied) meta verideki
    -0.1 ötelemesi ikinci kez uygulanmamalı; yoksa su pikselleri eksi yansıtıma düşer.
    """
    a = oge["assets"][ad]
    if ad == "scl":
        return a["href"], 1, 0.0
    p = oge["properties"]
    surum = float(p.get("s2:processing_baseline", "0") or 0)
    if p.get("earthsearch:boa_offset_applied") or surum < 4.0:
        oteleme = 0.0
    else:
        oteleme = -0.1
    return a["href"], 1e-4, oteleme


def olc(oge, kodlar, cer):
    tarih = oge["properties"]["datetime"][:10]
    sonuc = []
    gh, gs, go = bant(oge, "green")
    nh, ns, no = bant(oge, "nir")
    sh, _, _ = bant(oge, "scl")
    with rasterio.open(gh) as G, rasterio.open(nh) as N, rasterio.open(sh) as S:
        for kod in kodlar:
            c = cer[kod]
            x0, y0, x1, y1 = c["sinir"]
            b = G.bounds
            if x0 < b.left or x1 > b.right or y0 < b.bottom or y1 > b.top:
                continue
            w10 = from_bounds(x0, y0, x1, y1, G.transform).round_offsets().round_lengths()
            w20 = from_bounds(x0, y0, x1, y1, S.transform).round_offsets().round_lengths()
            yd = G.read(1, window=w10)
            nd = N.read(1, window=w10)
            sc = S.read(1, window=w20)
            sc = np.repeat(np.repeat(sc, 2, 0), 2, 1)[: yd.shape[0], : yd.shape[1]]
            if yd.shape != nd.shape or sc.shape != yd.shape:
                continue
            tr = G.window_transform(w10)
            maske = ~geometry_mask([c["geom"]], out_shape=yd.shape, transform=tr)
            r = alan_hesapla(yansitim(yd, gs, go), yansitim(nd, ns, no), sc, maske)
            sonuc.append({"kod": kod, "tarih": tarih, "goruntu": oge["id"],
                          "alan_km2": round(r["alan_km2"], 4) if r["alan_km2"] == r["alan_km2"] else "",
                          "ham_alan_km2": round(r["ham_alan_km2"], 4),
                          "gorunmez_oran": round(r["gorunmez_oran"], 4), "gecerli": int(r["gecerli"]),
                          "su_piksel": r["su_piksel"], "cerceve_piksel": r["cerceve_piksel"]})
    return sonuc


def mevcut():
    if not os.path.exists(CSV):
        return set()
    with open(CSV, encoding="utf8") as f:
        return {(r["kod"], r["goruntu"]) for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gun", type=int, default=None, help="yalnız son N gün")
    ap.add_argument("--paralel", type=int, default=12, help="eşzamanlı indirme sayısı")
    ap.add_argument("--kod", default=None, help="yalnız bu baraj(lar), virgülle")
    a = ap.parse_args()
    bugun = dt.date.today()
    bas = (bugun - dt.timedelta(days=a.gun)).isoformat() if a.gun else BASLANGIC
    cer = cerceveler()
    if a.kod:
        cer = {k: v for k, v in cer.items() if k in a.kod.split(",")}
    var = mevcut()
    isler = []
    for kare in sorted({c["kare"] for c in cer.values()}):
        kodlar = [k for k, c in cer.items() if c["kare"] == kare]
        ogeler = ara(kare, bas, bugun.isoformat())
        for o in ogeler:
            eksik = [k for k in kodlar if (k, o["id"]) not in var]
            if eksik:
                isler.append((o, eksik))
        print(f"{kare}: {len(ogeler)} görüntü, işlenecek {sum(1 for o, _ in isler if o['id'].split('_')[1] == kare)}", flush=True)
    yeni = not os.path.exists(CSV)
    os.makedirs("veri", exist_ok=True)
    kilit = threading.Lock()
    f = open(CSV, "a", newline="", encoding="utf8")
    yaz = csv.DictWriter(f, ALANLAR)
    if yeni:
        yaz.writeheader()
    bitti = hata = 0
    t0 = time.time()
    with ThreadPoolExecutor(a.paralel) as ex:
        gelecek = {ex.submit(olc, o, k, cer): o["id"] for o, k in isler}
        for g in as_completed(gelecek):
            try:
                satirlar = g.result()
            except Exception as e:
                hata += 1
                print("HATA", gelecek[g], str(e)[:200], file=sys.stderr, flush=True)
                continue
            with kilit:
                yaz.writerows(satirlar); f.flush()
            bitti += 1
            if bitti % 50 == 0:
                print(f"{bitti}/{len(isler)} görüntü, {time.time() - t0:.0f} sn", flush=True)
    f.close()
    print(f"bitti: {bitti} görüntü işlendi, {hata} hata")


if __name__ == "__main__":
    main()
