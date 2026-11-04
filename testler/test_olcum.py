import math
import numpy as np
import pytest

from olcum import alan_hesapla, ndwi, yansitim, aykiri_isaretle

SU = (0.08, 0.02)      # yeşil, nir: su (NDWI = 0.6)
KARA = (0.06, 0.30)    # bitki (NDWI ≈ −0.67)


def sahne(boy, su_maske):
    y = np.where(su_maske, SU[0], KARA[0]).astype("float32")
    n = np.where(su_maske, SU[1], KARA[1]).astype("float32")
    scl = np.where(su_maske, 6, 4).astype("uint8")
    return y, n, scl


def test_ndwi_isaret():
    v = ndwi(np.array([0.08, 0.06]), np.array([0.02, 0.30]))
    assert v[0] == pytest.approx(0.6)
    assert v[1] < 0


def test_tam_alan_10m_piksel():
    # 100x100 piksel çerçeve, sol yarısı su: 5000 piksel x 100 m² = 0.5 km²
    su = np.zeros((100, 100), bool); su[:, :50] = True
    y, n, scl = sahne(100, su)
    r = alan_hesapla(y, n, scl, np.ones((100, 100), bool))
    assert r["alan_km2"] == pytest.approx(0.5)
    assert r["ham_alan_km2"] == pytest.approx(0.5)
    assert r["gorunmez_oran"] == 0 and r["gecerli"]


def test_cerceve_disi_sayilmaz():
    su = np.ones((50, 50), bool)
    y, n, scl = sahne(50, su)
    cerceve = np.zeros((50, 50), bool); cerceve[10:20, 10:20] = True
    r = alan_hesapla(y, n, scl, cerceve)
    assert r["alan_km2"] == pytest.approx(100 * 100 / 1e6)


def test_az_bulut_duzeltme():
    # 1000 piksel çerçeve, %50 su; 20 piksel (%2) bulut -> geçerli, düzeltme görünen orana göre
    su = np.zeros((10, 100), bool); su[:, :50] = True
    y, n, scl = sahne(10, su)
    scl[0, 0:10] = 9   # 10 su pikseli bulutlu
    scl[0, 90:100] = 9  # 10 kara pikseli bulutlu
    r = alan_hesapla(y, n, scl, np.ones((10, 100), bool))
    assert r["gecerli"]
    assert r["gorunmez_oran"] == pytest.approx(0.02)
    assert r["ham_alan_km2"] == pytest.approx(490 * 100 / 1e6)
    assert r["alan_km2"] == pytest.approx(0.05)  # 490 + 20*490/980 = 500 piksel


def test_cok_bulut_gecersiz():
    su = np.ones((10, 10), bool)
    y, n, scl = sahne(10, su)
    scl[:5] = 8
    r = alan_hesapla(y, n, scl, np.ones((10, 10), bool))
    assert not r["gecerli"]
    assert r["gorunmez_oran"] == pytest.approx(0.5)


def test_tamamen_bulut_nan():
    y, n, scl = sahne(5, np.ones((5, 5), bool))
    scl[:] = 9
    r = alan_hesapla(y, n, scl, np.ones((5, 5), bool))
    assert math.isnan(r["alan_km2"]) and not r["gecerli"]


def test_nodata_gorunmez():
    y, n, scl = sahne(10, np.ones((10, 10), bool))
    y[:, :5] = np.nan
    r = alan_hesapla(y, n, scl, np.ones((10, 10), bool))
    assert r["gorunmez_oran"] == pytest.approx(0.5)


def test_bos_cerceve_hata():
    y, n, scl = sahne(3, np.ones((3, 3), bool))
    with pytest.raises(ValueError):
        alan_hesapla(y, n, scl, np.zeros((3, 3), bool))


def test_yansitim_oteleme():
    dn = np.array([0, 1000, 1800], dtype="uint16")
    r = yansitim(dn, 1e-4, -0.1)
    assert math.isnan(r[0])
    assert r[1] == pytest.approx(0.0, abs=1e-6)
    assert r[2] == pytest.approx(0.08)


def test_aykiri():
    tarihler = [f"2024-06-{g:02d}" for g in range(1, 29, 3)]
    alanlar = [20.0] * len(tarihler)
    alanlar[4] = 12.0
    s = aykiri_isaretle(tarihler, alanlar)
    assert s[4] and sum(s) == 1


def test_aykiri_serinin_sonu_gevsek():
    # son ölçümde %25 yükseliş: tek taraflı komşu -> eşik %30, şüpheli değil
    tarihler = [f"2024-06-{g:02d}" for g in range(1, 29, 3)]
    alanlar = [20.0] * (len(tarihler) - 1) + [25.0]
    assert not aykiri_isaretle(tarihler, alanlar)[-1]
    # aynı sıçrama ortada olursa şüpheli
    alanlar = [20.0] * len(tarihler); alanlar[4] = 25.0
    assert aykiri_isaretle(tarihler, alanlar)[4]
