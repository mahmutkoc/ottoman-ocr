import sys, os
sys.path.insert(0, r"C:\Users\user\ottoman-ocr")
os.chdir(r"C:\Users\user\ottoman-ocr")

from core.arabic_ocr import gorsel_dosya_to_arapca
from core.ottoman_transliteration import satirlar_transkribe, metin_transkribe

test_gorseller = [
    r"egitim verileri-20260603T164853Z-3-001\egitim verileri\0001.png",
    r"egitim verileri-20260603T164853Z-3-001\egitim verileri\0002.png",
    r"egitim verileri-20260603T164853Z-3-001\egitim verileri\0003.png",
]

import pandas as pd
df = pd.read_excel("osmanli_transkripsiyon.xlsx")

for gorsel in test_gorseller:
    fname = gorsel.split("\\")[-1]
    beklenen = df[df["file_name"] == fname]["text"].values
    beklenen_str = beklenen[0] if len(beklenen) > 0 else "?"

    print(f"=== {fname} ===")
    satirlar = gorsel_dosya_to_arapca(gorsel)
    arapca   = " | ".join(satirlar)
    latin    = satirlar_transkribe(satirlar)
    print(f"  Arapça   : {arapca}")
    print(f"  Latin    : {latin}")
    print(f"  Beklenen : {beklenen_str}")
    print()
