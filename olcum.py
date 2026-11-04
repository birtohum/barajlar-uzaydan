"""Bir Sentinel-2 görüntüsünden baraj su yüzeyi alanı hesabı (saf numpy; ağ yok, test edilebilir).

Yöntem
- NDWI (McFeeters 1996) = (Yeşil − YakınKızılötesi) / (Yeşil + YakınKızılötesi), 10 m bantlar (B03, B08).
- NDWI > ESIK olan piksel su sayılır.
- Bulut maskesi: Sen2Cor sahne sınıflandırması (SCL, 20 m → 10 m'ye en yakın komşu ile).
  Bulut, bulut gölgesi, ince sirrus, kar ve bozuk/boş pikseller "görünmez" kabul edilir.
- Yalnız baraj çerçevesi (OSM poligonu + küçük tampon) içindeki pikseller sayılır.
- Çerçevenin %ENFAZLA_GORUNMEZ'inden fazlası görünmezse ölçüm atılır (bulutlu gün).
  Daha az görünmez piksel varsa, bu piksellerin görünen kısımdaki su oranıyla dolu
  olduğu varsayılır (küçük bir düzeltme; kaydı ayrıca tutulur).
"""
import numpy as np

ESIK = 0.0
ENFAZLA_GORUNMEZ = 0.03
PIKSEL_M2 = 100.0  # 10 m x 10 m

# SCL sınıfları: 0 boş, 1 doymuş/bozuk, 2 karanlık alan, 3 bulut gölgesi, 4 bitki, 5 çıplak toprak,
# 6 su, 7 sınıflanmamış, 8 orta olasılık bulut, 9 yüksek olasılık bulut, 10 ince sirrus, 11 kar/buz
GORUNMEZ_SCL = (0, 1, 3, 8, 9, 10, 11)


def ndwi(yesil, nir):
    yesil = yesil.astype("float32")
    nir = nir.astype("float32")
    toplam = yesil + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        n = (yesil - nir) / toplam
    n[~np.isfinite(n)] = np.nan
    return n


def alan_hesapla(yesil, nir, scl, cerceve, esik=ESIK, enfazla_gorunmez=ENFAZLA_GORUNMEZ, piksel_m2=PIKSEL_M2):
    """yesil, nir: yansıtım (ölçek/öteleme uygulanmış, float). scl: SCL sınıfları (aynı şekil).
    cerceve: bool dizi, baraj çerçevesi içindeki pikseller.

    Dönüş: dict(alan_km2, ham_alan_km2, gorunmez_oran, gecerli, su_piksel, cerceve_piksel)
    """
    cerceve = cerceve.astype(bool)
    n_cerceve = int(cerceve.sum())
    if n_cerceve == 0:
        raise ValueError("çerçeve boş")
    n = ndwi(yesil, nir)
    gorunmez = np.isin(scl, GORUNMEZ_SCL) | np.isnan(n) | (yesil <= -0.05)
    gorunur = cerceve & ~gorunmez
    su = gorunur & (n > esik)
    n_gorunur = int(gorunur.sum())
    n_su = int(su.sum())
    gorunmez_oran = 1.0 - n_gorunur / n_cerceve
    ham = n_su * piksel_m2 / 1e6
    if n_gorunur == 0:
        duzeltilmis = float("nan")
    else:
        duzeltilmis = (n_su + (n_cerceve - n_gorunur) * n_su / n_gorunur) * piksel_m2 / 1e6
    return {
        "alan_km2": duzeltilmis,
        "ham_alan_km2": ham,
        "gorunmez_oran": gorunmez_oran,
        "gecerli": gorunmez_oran <= enfazla_gorunmez,
        "su_piksel": n_su,
        "cerceve_piksel": n_cerceve,
    }


def yansitim(dn, olcek=1e-4, oteleme=0.0, nodata=0):
    """Ham sayısal değeri (DN) yansıtıma çevirir; nodata NaN olur."""
    r = dn.astype("float32") * olcek + oteleme
    r[dn == nodata] = np.nan
    return r


def aykiri_isaretle(tarihler, alanlar, pencere_gun=45, esik=0.15, komsu_sayisi=6, en_az_komsu=2):
    """Zaman serisinde zamanca en yakın komşularının medyanından göreli olarak çok sapan ölçümleri işaretler.

    Barajlar birkaç günde %15 küçülüp büyümez; böyle sıçramalar çoğunlukla bulut maskesinin
    kaçırdığı sis/pus ya da kısmi görüntüdür. Komşular: ±pencere_gun içindeki en yakın
    komsu_sayisi ölçüm (kendisi hariç). Komşuların hepsi tek taraftaysa (ör. serinin son günleri)
    eşik iki katına çıkar: yağışla gelen gerçek bir yükselişi, doğrulayacak sonraki ölçüm gelmeden
    silmemek için. Dönüş: bool liste (True = şüpheli).
    """
    t = np.array([np.datetime64(x, "D").astype("int64") for x in tarihler])
    a = np.asarray(alanlar, dtype=float)
    supheli = np.zeros(len(a), dtype=bool)
    for i in range(len(a)):
        fark = np.abs(t - t[i]).astype(float)
        fark[i] = np.inf
        aday = np.where(fark <= pencere_gun)[0]
        if len(aday) < en_az_komsu:
            continue
        komsu = aday[np.argsort(fark[aday])[:komsu_sayisi]]
        m = np.median(a[komsu])
        iki_taraf = (t[komsu] < t[i]).any() and (t[komsu] > t[i]).any()
        e = esik if iki_taraf else 2 * esik
        if m > 0 and abs(a[i] - m) / m > e:
            supheli[i] = True
    return supheli.tolist()
