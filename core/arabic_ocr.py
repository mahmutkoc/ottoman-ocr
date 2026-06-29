"""
Aşama 1: Görsel → Arap harfli metin
EasyOCR Arapça modeli ile tamamen offline çalışır.
Model ilk çalıştırmada ~/.EasyOCR/model/ altına indirilir (~200MB), sonrası internetsiz.
"""

import io
import base64
import logging
from functools import lru_cache

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_reader():
    """EasyOCR Reader'ı bir kez oluştur, önbellekte tut. GPU varsa kullanır, yoksa CPU'ya düşer."""
    import easyocr
    import torch
    return easyocr.Reader(
        ['ar'],
        gpu=torch.cuda.is_available(),
        verbose=False,
    )


def gorsel_to_arapca(image: Image.Image, min_guven: float = 0.2) -> list[str]:
    """
    PIL Image → tespit edilen Arapça metin satırları listesi.
    Satırlar yukarıdan aşağıya sıralanır.
    """
    reader    = _get_reader()
    img_array = np.array(image.convert("RGB"))

    result = reader.readtext(img_array, detail=1, paragraph=False)

    if not result:
        return []

    # Kutular: (bbox, text, confidence)
    # bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    # Yukarıdan aşağıya sırala
    result_sirali = sorted(result, key=lambda x: x[0][0][1])

    # Güven filtresi uygula
    result_sirali = [(b, m, g) for (b, m, g) in result_sirali if g >= min_guven and m.strip()]

    if not result_sirali:
        return []

    # Satır birleştirme: y-merkezi yakın kutular aynı satır sayılır
    # Tolerans: kutunun ortalama yüksekliğinin %60'ı
    def y_merkez(bbox):
        return (bbox[0][1] + bbox[2][1]) / 2

    def x_merkez(bbox):
        return (bbox[0][0] + bbox[2][0]) / 2

    def kutu_yuksekligi(bbox):
        return abs(bbox[2][1] - bbox[0][1])

    satirlar_ham = []  # [(y_merkez, yukseklik, x_merkez, metin)]
    for (bbox, metin, _) in result_sirali:
        satirlar_ham.append((y_merkez(bbox), kutu_yuksekligi(bbox), x_merkez(bbox), metin.strip()))

    # Ortalama kutu yüksekliği
    ort_yukseklik = sum(y for _, y, _, _ in satirlar_ham) / len(satirlar_ham)
    tolerans = ort_yukseklik * 0.6

    # Yakın y-merkezleri aynı satırda birleştir
    gruplar = []  # [(y_merkez, [(x_merkez, metin), ...])]
    for (ym, _, xm, metin) in satirlar_ham:
        eklendi = False
        for grup in gruplar:
            if abs(ym - grup[0]) <= tolerans:
                grup[1].append((xm, metin))
                # Grup y-merkezini güncelle
                grup[0] = (grup[0] + ym) / 2
                eklendi = True
                break
        if not eklendi:
            gruplar.append([ym, [(xm, metin)]])

    # Her grubu tek satır olarak birleştir (Arapça sağdan sola → x'e göre büyükten küçüğe)
    satirlar = []
    for (_, kelimeler) in sorted(gruplar, key=lambda g: g[0]):
        kelimeler_sirali = sorted(kelimeler, key=lambda k: -k[0])
        birlesik = " ".join(metin for _, metin in kelimeler_sirali)
        if birlesik.strip():
            satirlar.append(birlesik.strip())

    return satirlar


def gorsel_b64_to_arapca(image_b64: str) -> list[str]:
    """Base64 görsel → Arapça satır listesi."""
    img_bytes = base64.b64decode(image_b64)
    image     = Image.open(io.BytesIO(img_bytes))
    return gorsel_to_arapca(image)


def gorsel_dosya_to_arapca(dosya_yolu: str) -> list[str]:
    """Dosya yolundan → Arapça satır listesi."""
    return gorsel_to_arapca(Image.open(dosya_yolu))
