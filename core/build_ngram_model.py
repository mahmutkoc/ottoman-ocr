"""
Eğitim verisindeki Latin transkripsiyonlardan bigram (kelime çifti)
frekans modeli oluşturur. Sesli harf tamamlamada bağlama göre
doğru adayı seçmek için kullanılır.

Çıktı: core/bigram_model.json  → {onceki_kelime: {sonraki_kelime: frekans}}
"""

import json
import re
from pathlib import Path
import pandas as pd

NORMALIZASYON = str.maketrans("âîû", "aiu")


def normalize(kelime: str) -> str:
    return kelime.lower().translate(NORMALIZASYON)


def temizle(kelime: str) -> str:
    temiz = re.sub(r"[^\w''\-âîûÂÎÛ]", "", kelime, flags=re.UNICODE)
    return temiz.strip("'-")


def bigram_olustur(xlsx_yolu: str) -> dict:
    df = pd.read_excel(xlsx_yolu)
    bigram = {}  # onceki_kelime → {sonraki_kelime: frekans}

    for metin in df["text"].dropna():
        kelimeler = [normalize(temizle(k)) for k in str(metin).split()]
        kelimeler = [k for k in kelimeler if len(k) >= 2]

        for onceki, sonraki in zip(kelimeler, kelimeler[1:]):
            if onceki not in bigram:
                bigram[onceki] = {}
            bigram[onceki][sonraki] = bigram[onceki].get(sonraki, 0) + 1

    return bigram


if __name__ == "__main__":
    xlsx  = Path(r"C:\Users\user\ottoman-ocr\osmanli_transkripsiyon.xlsx")
    cikti = Path(r"C:\Users\user\ottoman-ocr\core\bigram_model.json")

    print("Bigram modeli oluşturuluyor...")
    bigram = bigram_olustur(str(xlsx))
    toplam_cift = sum(len(v) for v in bigram.values())
    print(f"  {len(bigram)} benzersiz öncül kelime, {toplam_cift} kelime çifti")

    cikti.write_text(json.dumps(bigram, ensure_ascii=False), encoding="utf-8")
    print(f"Kaydedildi: {cikti}")
