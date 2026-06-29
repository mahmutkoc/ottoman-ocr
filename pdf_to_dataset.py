"""
PDF → Osmanlıca OCR Eğitim Veri Seti
======================================
PDF Yapısı:
  - İlk yarı  : Latin transkripsiyon sayfaları (mavi başlıkta belge no)
  - İkinci yarı: Osmanlıca belge görselleri    (sağda mavi kutuda belge no)

Eşleştirme: Her iki bölümde de büyük belge numarası (1-58) eşleştirme anahtarı.

Kurulum:
    pip install pymupdf pandas openpyxl
"""

import re
import json
from pathlib import Path

import fitz  # pymupdf
import pandas as pd

# ── Ayarlar ──────────────────────────────────────────────
PDF_YOLU   = Path(r"C:\Users\user\Downloads\bf1610ef-7022-4d92-91ec-32dcbc8590eb.pdf")
CIKTI_DIR  = Path(r"C:\Users\user\ottoman-ocr\pdf_dataset")
XLSX_YOLU  = Path(r"C:\Users\user\ottoman-ocr\osmanli_transkripsiyon.xlsx")
DPI        = 250   # Görsel çözünürlük (yüksek = daha iyi OCR, daha büyük dosya)
# ─────────────────────────────────────────────────────────

CIKTI_DIR.mkdir(exist_ok=True)
(CIKTI_DIR / "images").mkdir(exist_ok=True)


def sayfa_belge_no(sayfa: fitz.Page) -> int | None:
    """
    Sayfadaki büyük belge numarasını bul.
    Mavi kutudaki "12", "8" gibi tek başına duran sayılar.
    Strateji: Büyük font boyutundaki sayısal blokları ara.
    """
    blocks = sayfa.get_text("dict")["blocks"]
    for block in blocks:
        if block.get("type") != 0:  # sadece metin blokları
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text  = span["text"].strip()
                fsize = span["size"]
                # Tek başına 1-3 haneli sayı + büyük font (≥18pt) → belge numarası
                if re.match(r"^\d{1,2}$", text) and fsize >= 18:
                    return int(text)
    return None


def sayfa_turu(sayfa: fitz.Page) -> str:
    """
    'transkripsiyon' mu 'gorsel' mi?
    Latin karakter yoğunluğuna göre karar ver.
    """
    metin = sayfa.get_text()
    latin = sum(1 for c in metin if c.isascii() and c.isalpha())
    # Görsel sayfa: taranmış belge → az Latin metin, büyük resim var
    resimler = sayfa.get_images(full=False)
    if resimler and latin < 100:
        return "gorsel"
    if latin > 80:
        return "transkripsiyon"
    return "bilinmiyor"


def pdf_isle(doc: fitz.Document):
    """
    PDF'yi tara, sayfaları sınıflandır.
    Dönüş: (transkripsiyon_dict, gorsel_dict)
      transkripsiyon_dict: {belge_no: [metin, metin, ...]}
      gorsel_dict        : {belge_no: [sayfa_index, ...]}
    """
    print(f"Toplam PDF sayfası: {len(doc)}")

    trans_dict  = {}   # {belge_no: [metin satırları]}
    gorsel_dict = {}   # {belge_no: [sayfa_indexleri]}

    guncel_belge_no_trans  = None
    guncel_belge_no_gorsel = None

    for i, sayfa in enumerate(doc):
        tur = sayfa_turu(sayfa)
        belge_no = sayfa_belge_no(sayfa)

        if tur == "transkripsiyon":
            if belge_no:
                guncel_belge_no_trans = belge_no
                trans_dict[belge_no] = []
            if guncel_belge_no_trans:
                metin = sayfa.get_text().strip()
                trans_dict[guncel_belge_no_trans].append(metin)

        elif tur == "gorsel":
            if belge_no:
                guncel_belge_no_gorsel = belge_no
                gorsel_dict[belge_no] = []
            if guncel_belge_no_gorsel:
                gorsel_dict[guncel_belge_no_gorsel].append(i)

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(doc)} sayfa işlendi...")

    return trans_dict, gorsel_dict


def metin_temizle(metin_listesi: list[str], belge_no: int) -> str:
    """
    Transkripsiyon sayfalarından gelen ham metni temizle.
    - Sayfa üst/alt bilgilerini çıkar (kitap başlığı, sayfa no)
    - Belge numarası başlık satırını çıkar
    - Arşiv referanslarını çıkar (BOA, ...)
    """
    birlesik = "\n".join(metin_listesi)
    satirlar = birlesik.split("\n")

    temiz = []
    for satir in satirlar:
        s = satir.strip()
        if not s:
            continue
        # Sayfa numarası (tek başına rakam)
        if re.match(r"^\d{1,3}$", s):
            continue
        # Kitap başlığı
        if "Ermeni Sevk" in s or "İskânının" in s:
            continue
        # Belge numarası başlığı (büyük tek sayı zaten ayraç olarak kullanıldı)
        if s == str(belge_no):
            continue
        # Arşiv referansı (BOA, ...)
        if s.startswith("BOA") or s.startswith("**"):
            continue
        # Yayın bilgisi
        if s.startswith("Düstûr") or s.startswith("∗∗") or s == "**":
            continue
        temiz.append(s)

    return "\n".join(temiz).strip()


def gorsel_kaydet(sayfa: fitz.Page, dosya_adi: str) -> Path:
    """Sayfayı yüksek çözünürlüklü PNG olarak kaydet."""
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = sayfa.get_pixmap(matrix=mat)
    yol = CIKTI_DIR / "images" / dosya_adi
    pix.save(str(yol))
    return yol


def veri_seti_olustur(doc, trans_dict, gorsel_dict) -> list[dict]:
    """
    Transkripsiyon + görselleri eşleştir, dataset satırları üret.
    Bir belgenin birden fazla görsel sayfası varsa her biri ayrı satır olur
    (aynı transkripsiyon, farklı görsel).
    """
    ortak_belgeler = sorted(set(trans_dict.keys()) & set(gorsel_dict.keys()))
    print(f"\nTranskripsiyon bulunan belge: {len(trans_dict)}")
    print(f"Görsel bulunan belge        : {len(gorsel_dict)}")
    print(f"Eşleşen belge               : {len(ortak_belgeler)}")

    satirlar = []
    for belge_no in ortak_belgeler:
        transkripsiyon = metin_temizle(trans_dict[belge_no], belge_no)
        if not transkripsiyon:
            print(f"  [ATLA] Belge {belge_no}: transkripsiyon boş")
            continue

        gorsel_sayfalar = gorsel_dict[belge_no]
        for idx, sayfa_i in enumerate(gorsel_sayfalar):
            dosya_adi = f"pdf_belge_{belge_no:03d}_{idx+1:02d}.png"
            gorsel_yolu = gorsel_kaydet(doc[sayfa_i], dosya_adi)
            satirlar.append({
                "file_name": dosya_adi,
                "text"     : transkripsiyon,
            })
            print(f"  ✓ Belge {belge_no:2d} / Sayfa {idx+1} → {dosya_adi}")

    return satirlar


def xlsx_guncelle(satirlar: list[dict]):
    """Mevcut xlsx'e yeni satırlar ekle (tekrar ekleme yapma)."""
    yeni_df = pd.DataFrame(satirlar)[["file_name", "text"]]

    if XLSX_YOLU.exists():
        mevcut    = pd.read_excel(XLSX_YOLU)
        mevcut_fn = set(mevcut["file_name"].tolist())
        yeni      = yeni_df[~yeni_df["file_name"].isin(mevcut_fn)]
        if len(yeni) == 0:
            print("\nTüm belgeler zaten xlsx'te mevcut — güncelleme yapılmadı.")
            return
        birlesik = pd.concat([mevcut, yeni], ignore_index=True)
        print(f"\n{len(yeni)} yeni satır eklendi (önceki: {len(mevcut)}, yeni toplam: {len(birlesik)})")
    else:
        birlesik = yeni_df
        print(f"\nYeni xlsx oluşturuldu: {len(birlesik)} satır")

    birlesik.to_excel(XLSX_YOLU, index=False)
    print(f"Kaydedildi → {XLSX_YOLU}")


def kontrol_raporu(trans_dict, gorsel_dict):
    """Eşleşmeyen belgeleri raporla."""
    sadece_trans  = set(trans_dict.keys()) - set(gorsel_dict.keys())
    sadece_gorsel = set(gorsel_dict.keys()) - set(trans_dict.keys())
    if sadece_trans:
        print(f"\n[UYARI] Görseli olmayan transkripsiyon: {sorted(sadece_trans)}")
    if sadece_gorsel:
        print(f"[UYARI] Transkripsiyonu olmayan görsel : {sorted(sadece_gorsel)}")


def main():
    print("=" * 60)
    print("PDF → Osmanlıca OCR Veri Seti")
    print("=" * 60)

    if not PDF_YOLU.exists():
        print(f"[HATA] PDF bulunamadı: {PDF_YOLU}")
        return

    doc = fitz.open(str(PDF_YOLU))

    # 1. PDF'yi tara
    trans_dict, gorsel_dict = pdf_isle(doc)

    # 2. Kontrol raporu
    kontrol_raporu(trans_dict, gorsel_dict)

    if not trans_dict:
        print("\n[HATA] Transkripsiyon metni bulunamadı.")
        print("İlk 5 sayfanın metin içeriğini debug.txt'e yazıyorum...")
        with open(CIKTI_DIR / "debug.txt", "w", encoding="utf-8") as f:
            for i in range(min(5, len(doc))):
                f.write(f"\n{'='*40}\nSAYFA {i+1}\n{'='*40}\n")
                f.write(doc[i].get_text())
        print(f"→ {CIKTI_DIR / 'debug.txt'} dosyasına bakın.")
        return

    # 3. Veri seti oluştur
    satirlar = veri_seti_olustur(doc, trans_dict, gorsel_dict)

    if not satirlar:
        print("\n[HATA] Hiç eşleşme yapılamadı.")
        return

    # 4. JSON özet kaydet
    ozet = CIKTI_DIR / "eslesmeler.json"
    with open(ozet, "w", encoding="utf-8") as f:
        # Transkripsiyon metnini kısalt (debug için)
        ozet_veri = [{"file_name": s["file_name"], "text_preview": s["text"][:100]} for s in satirlar]
        json.dump(ozet_veri, f, ensure_ascii=False, indent=2)

    # 5. xlsx güncelle
    xlsx_guncelle(satirlar)

    print(f"\n{'='*60}")
    print(f"✓ TAMAMLANDI")
    print(f"  {len(satirlar)} eğitim satırı oluşturuldu")
    print(f"  Görseller  : {CIKTI_DIR / 'images'}")
    print(f"  xlsx       : {XLSX_YOLU}")
    print(f"  Özet       : {ozet}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
