"""Onaylanan belgeleri veri setine kaydeder."""

import json
import shutil
from pathlib import Path
from datetime import date

VERI_SETI = Path.home() / "osmanli_veri_seti"
VERI_KLASORU = VERI_SETI / "veri_seti"
ISTATISTIK = VERI_SETI / "istatistik.json"

BOSLUK_ISTATISTIK = {
    "toplam_belge": 0,
    "hedef": 10000,
    "belge_turleri": {
        "ferman": 0, "mektup": 0, "senet": 0,
        "berat": 0, "sicil": 0, "arzuhal": 0, "diger": 0
    },
    "hat_stilleri": {
        "nesih": 0, "rika": 0, "talik": 0, "divani": 0, "matbu": 0
    },
    "son_guncelleme": str(date.today())
}


def _istatistik_oku() -> dict:
    if ISTATISTIK.exists():
        return json.loads(ISTATISTIK.read_text(encoding="utf-8"))
    return BOSLUK_ISTATISTIK.copy()


def _istatistik_yaz(ist: dict):
    ISTATISTIK.parent.mkdir(parents=True, exist_ok=True)
    ISTATISTIK.write_text(json.dumps(ist, ensure_ascii=False, indent=2), encoding="utf-8")


def _sonraki_id() -> str:
    VERI_KLASORU.mkdir(parents=True, exist_ok=True)
    mevcut = [int(p.name) for p in VERI_KLASORU.iterdir()
              if p.is_dir() and p.name.isdigit()]
    return str(max(mevcut, default=0) + 1).zfill(4)


def kaydet(
    goruntu_bytes: bytes,
    dosya_adi: str,
    analiz_sonucu: str,
    belge_turu: str,
    hat_stili: str,
    etiketleyen: str = "Mahmut Koç"
) -> str:
    """
    Onaylanan belgeyi veri setine kaydet.
    Döndürür: oluşturulan klasör ID'si
    """
    yeni_id = _sonraki_id()
    klasor = VERI_KLASORU / yeni_id
    klasor.mkdir(parents=True, exist_ok=True)

    # Görseli kaydet
    uzanti = Path(dosya_adi).suffix or ".jpg"
    goruntu_yolu = klasor / f"goruntu{uzanti}"
    goruntu_yolu.write_bytes(goruntu_bytes)

    # Analiz metnini parse ederek JSON oluştur
    etiket = {
        "id": yeni_id,
        "meta": {
            "belge_turu": belge_turu,
            "hat_stili": hat_stili,
            "kaynak": dosya_adi,
            "etiketleyen": etiketleyen,
            "etiket_tarihi": str(date.today()),
            "uzman_onayladi": True
        },
        "ham_analiz": analiz_sonucu
    }

    etiket_yolu = klasor / "etiket.json"
    etiket_yolu.write_text(json.dumps(etiket, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ham analizi de txt olarak kaydet (kolay okuma için)
    (klasor / "analiz.txt").write_text(analiz_sonucu, encoding="utf-8")

    # İstatistiği güncelle
    ist = _istatistik_oku()
    ist["toplam_belge"] += 1
    ist["belge_turleri"][belge_turu] = ist["belge_turleri"].get(belge_turu, 0) + 1
    ist["hat_stilleri"][hat_stili] = ist["hat_stilleri"].get(hat_stili, 0) + 1
    ist["son_guncelleme"] = str(date.today())
    _istatistik_yaz(ist)

    return yeni_id


def istatistik_getir() -> dict:
    return _istatistik_oku()
