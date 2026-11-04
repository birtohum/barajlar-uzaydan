"""veri/olcumler.csv -> site/veri/*.json + site/gorsel/* (uydu görüntüsü kırpıntıları, su siluetleri)

- Bulutlu (gecerli=0) ve zaman serisinde sıçrama yapan (şüpheli) ölçümler grafiğe girmez.
- "En dolu" = baraj için 2017'den beri temiz ölçümlerin 98. yüzdeliği (tek tük hatalı yüksek değere karşı).
- Önce/şimdi görüntüleri: son 365 gündeki en geniş su yüzeyi günü ve son temiz gün.
"""
import csv, datetime as dt, json, os, sys, warnings
from collections import defaultdict

warnings.filterwarnings("ignore")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")

import numpy as np

from barajlar import BARAJLAR
from olcum import aykiri_isaretle, ndwi, yansitim, ESIK

CSV = "veri/olcumler.csv"
ISKI = "veri/iski/gunluk_doluluk.xlsx"
SITE = "site"
KUCUK = ("istrancalar", "elmali", "kazandere", "pabucdere")  # küçük ya da hızlı dolup boşalan göller


def oku():
    seri = defaultdict(list)
    with open(CSV, encoding="utf8") as f:
        for r in csv.DictReader(f):
            if r["gecerli"] == "1" and r["alan_km2"]:
                seri[r["kod"]].append((r["tarih"], float(r["alan_km2"]), r["goruntu"], float(r["gorunmez_oran"])))
    for k in seri:
        seri[k].sort()
        # aynı gün iki görüntü olabilir (iki uydu geçişi): bulutu az olanı tut
        gun = {}
        for t, a, g, b in seri[k]:
            if t not in gun or b < gun[t][3]:
                gun[t] = (t, a, g, b)
        seri[k] = sorted(gun.values())
    return seri


def iski_oku():
    if not os.path.exists(ISKI):
        return {}
    import pandas as pd
    d = pd.read_excel(ISKI)
    # Dosyada 130 satırın tarihi metin ("1.4.2023", gün.ay.yıl); geri kalanı Excel tarihi.
    d["Tarih"] = d["Tarih"].map(lambda x: dt.datetime.strptime(x, "%d.%m.%Y") if isinstance(x, str) else x)
    d["Tarih"] = pd.to_datetime(d["Tarih"])
    d = d[d["Tarih"] >= "2017-01-01"]
    sonuc = {}
    for b in BARAJLAR:
        if b["ad"] in d.columns:
            s = d[["Tarih", b["ad"]]].dropna()
            sonuc[b["kod"]] = {t.strftime("%Y-%m-%d"): float(v) / (100 if float(v) > 1.5 else 1) for t, v in zip(s["Tarih"], s[b["ad"]])}
    return sonuc


def spearman(x, y):
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def _pencereler(geom):
    """Kırpılacak pencereler. Birbirinden uzak parçalı göllerde (Istrancalar) her parça ayrı kırpılır."""
    def kutu(g):
        x0, y0, x1, y1 = g.bounds
        pay = max(x1 - x0, y1 - y0) * 0.08 + 60
        return (np.floor((x0 - pay) / 20) * 20, np.floor((y0 - pay) / 20) * 20,
                np.ceil((x1 + pay) / 20) * 20, np.ceil((y1 + pay) / 20) * 20)
    tum = kutu(geom)
    if geom.geom_type == "MultiPolygon":
        parcalar = sorted([kutu(p) for p in geom.geoms if p.area > 2e4], key=lambda k: k[0])
        toplam = sum((k[2] - k[0]) * (k[3] - k[1]) for k in parcalar)
        if (tum[2] - tum[0]) * (tum[3] - tum[1]) > 15 * toplam:
            return parcalar
    return [tum]


def _yan_yana(resimler, yukseklik, mod):
    from PIL import Image
    olcekli = [r.resize((max(1, round(r.width * yukseklik / r.height)), yukseklik), Image.LANCZOS) for r in resimler]
    bosluk = 12 if len(olcekli) > 1 else 0
    W = sum(r.width for r in olcekli) + bosluk * (len(olcekli) - 1)
    tuval = Image.new(mod, (W, yukseklik), (0, 0, 0, 0) if mod == "RGBA" else (246, 241, 231))
    x = 0
    for r in olcekli:
        tuval.paste(r, (x, 0)); x += r.width + bosluk
    return tuval


def gorseller(b, cer, once, simdi, hedef):
    """Önce/şimdi gerçek renkli kırpıntılar + iki tarihin su maskesinden siluet PNG'si."""
    import rasterio
    from PIL import Image
    from rasterio.windows import from_bounds
    from rasterio.features import geometry_mask
    import cek
    c = cer[b["kod"]]
    pencereler = _pencereler(c["geom"])
    maskeler = {}
    for ad, (tarih, _, goruntu, _) in (("once", once), ("simdi", simdi)):
        oge = [o for o in cek.ara(b["kare"], tarih, tarih) if o["id"] == goruntu][0]
        gh, gs, go = cek.bant(oge, "green"); nh, ns, no = cek.bant(oge, "nir")
        rgbler, mler = [], []
        with rasterio.open(oge["assets"]["visual"]["href"]) as V, rasterio.open(gh) as G, rasterio.open(nh) as N:
            for (x0, y0, x1, y1) in pencereler:
                w = from_bounds(x0, y0, x1, y1, V.transform).round_offsets().round_lengths()
                rgb = V.read(window=w, boundless=True, fill_value=0).transpose(1, 2, 0)
                tr = V.window_transform(w)
                g = yansitim(G.read(1, window=w, boundless=True, fill_value=0), gs, go)
                n = yansitim(N.read(1, window=w, boundless=True, fill_value=0), ns, no)
                icinde = ~geometry_mask([c["geom"]], out_shape=g.shape, transform=tr)
                mler.append((ndwi(g, n) > ESIK) & icinde)
                rgbler.append(rgb)
        maskeler[ad] = mler
        # hafif parlaklık/kontrast germe: TCI görüntüleri koyu görünür
        tum = np.concatenate([r.reshape(-1, 3) for r in rgbler]).astype("float32")
        alt, ust = np.percentile(tum, 1), np.percentile(tum, 99.5)
        resimler = [Image.fromarray(np.clip((r.astype("float32") - alt) / (ust - alt) * 255, 0, 255).astype("uint8")) for r in rgbler]
        img = _yan_yana(resimler, min(1000, max(r.height for r in resimler)), "RGB")
        img.thumbnail((1000, 1000), Image.LANCZOS)
        img.save(f"{hedef}/{b['kod']}_{ad}.jpg", quality=82, optimize=True)
    siluetler = []
    for mo, ms in zip(maskeler["once"], maskeler["simdi"]):
        s = np.zeros(mo.shape + (4,), "uint8")
        s[mo] = (231, 184, 116, 255)          # kuruyan kıyı (önce su, şimdi değil): kum rengi
        s[ms] = (25, 118, 210, 255)           # şimdi su: mavi
        siluetler.append(Image.fromarray(s))
    img = _yan_yana(siluetler, max(s.height for s in siluetler), "RGBA")
    img.thumbnail((700, 700), Image.LANCZOS)
    img.save(f"{hedef}/{b['kod']}_siluet.png", optimize=True)


def main():
    yeniden_gorsel = "--gorsel" in sys.argv
    seri = oku()
    iski = iski_oku()
    os.makedirs(f"{SITE}/veri", exist_ok=True)
    os.makedirs(f"{SITE}/gorsel", exist_ok=True)
    meta_yolu = f"{SITE}/gorsel/meta.json"
    meta = json.load(open(meta_yolu, encoding="utf8")) if os.path.exists(meta_yolu) else {}
    cer = None
    ozet = []
    bugun = dt.date.today()
    for b in BARAJLAR:
        s = seri.get(b["kod"], [])
        if len(s) < 10:
            print(b["ad"], "yetersiz veri", file=sys.stderr); continue
        tarihler = [x[0] for x in s]; alanlar = [x[1] for x in s]
        supheli = aykiri_isaretle(tarihler, alanlar, esik=0.15 if b["kod"] not in KUCUK else 0.25)
        temiz = [x for x, sp in zip(s, supheli) if not sp]
        dolu = float(np.percentile([x[1] for x in temiz], 98))
        son = temiz[-1]
        son_t = dt.date.fromisoformat(son[0])
        yil_once = [x for x in temiz if abs((dt.date.fromisoformat(x[0]) - (son_t - dt.timedelta(days=365))).days) <= 15]
        gecen_yil = float(np.median([x[1] for x in yil_once])) if yil_once else None
        son365 = [x for x in temiz if (son_t - dt.date.fromisoformat(x[0])).days <= 365]
        once = max(son365, key=lambda x: x[1])
        if (son_t - dt.date.fromisoformat(once[0])).days < 30:   # en dolu gün zaten şimdi: en kuruya bak
            once = min(son365, key=lambda x: x[1])
        # ISKI karşılaştırması (2017 - Şubat 2024)
        karsi = None
        if b["kod"] in iski:
            eslesen = [(x[1], iski[b["kod"]][x[0]]) for x in temiz if x[0] in iski[b["kod"]]]
            if len(eslesen) > 20:
                a_, d_ = np.array(eslesen).T
                karsi = {"n": len(eslesen), "spearman": round(spearman(a_, d_), 3),
                         "seri": [[t, round(v * 100, 1)] for t, v in sorted(iski[b["kod"]].items())][::3]}
        kayit = {
            "kod": b["kod"], "ad": b["ad"], "yaka": b["yaka"], "not": b.get("not"),
            "dolu_km2": round(dolu, 3),
            "son": {"tarih": son[0], "km2": round(son[1], 3), "yuzde": round(100 * son[1] / dolu, 1)},
            "gecen_yil": {"km2": round(gecen_yil, 3), "yuzde": round(100 * gecen_yil / dolu, 1)} if gecen_yil else None,
            "once": {"tarih": once[0], "km2": round(once[1], 3)},
            "olcum_sayisi": len(temiz), "supheli_sayisi": int(sum(supheli)),
            "ilk_tarih": temiz[0][0],
            "iski": {"n": karsi["n"], "spearman": karsi["spearman"]} if karsi else None,
        }
        ozet.append(kayit)
        detay = dict(kayit)
        detay["seri"] = [[x[0], round(x[1], 3)] for x in temiz]
        detay["supheli"] = [[x[0], round(x[1], 3)] for x, sp in zip(s, supheli) if sp]
        detay["iski_seri"] = karsi["seri"] if karsi else None
        json.dump(detay, open(f"{SITE}/veri/{b['kod']}.json", "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
        anahtar = f"{once[2]}|{son[2]}"
        if yeniden_gorsel or meta.get(b["kod"]) != anahtar or not os.path.exists(f"{SITE}/gorsel/{b['kod']}_siluet.png"):
            if cer is None:
                import cek
                cer = cek.cerceveler()
            print("görsel:", b["ad"], once[0], "->", son[0], flush=True)
            gorseller(b, cer, once, son, f"{SITE}/gorsel")
            meta[b["kod"]] = anahtar
            json.dump(meta, open(meta_yolu, "w", encoding="utf8"), indent=1)
        print(f"{b['ad']:13s} son {son[0]} {son[1]:7.2f} km² (%{kayit['son']['yuzde']:.0f})  dolu {dolu:6.2f}  "
              f"temiz {len(temiz)} şüpheli {sum(supheli)}  İSKİ ρ={karsi['spearman'] if karsi else '-'}")
    toplam_son = sum(o["son"]["km2"] for o in ozet); toplam_dolu = sum(o["dolu_km2"] for o in ozet)
    json.dump({"guncelleme": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
               "toplam": {"son_km2": round(toplam_son, 2), "dolu_km2": round(toplam_dolu, 2),
                          "yuzde": round(100 * toplam_son / toplam_dolu, 1)},
               "barajlar": ozet},
              open(f"{SITE}/veri/ozet.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    surum_damgasi()


def surum_damgasi():
    """index.html'deki stil/betik adreslerine içerik özeti ekler: tarayıcı önbelleği eski dosyayı tutmasın."""
    import hashlib, re
    yol = f"{SITE}/index.html"
    h = open(yol, encoding="utf8").read()
    for ad in ("stil.css", "uygulama.js"):
        oz = hashlib.sha1(open(f"{SITE}/{ad}", "rb").read()).hexdigest()[:8]
        h = re.sub(re.escape(ad) + r"\?v=[0-9a-z]+", f"{ad}?v={oz}", h)
    open(yol, "w", encoding="utf8", newline="\n").write(h)


if __name__ == "__main__":
    main()
