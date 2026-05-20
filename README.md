# Osmanlıca Metin Okuyucu

## Kurulum

### 1. Bağımlılıkları kur

```bash
cd ottoman_ocr
pip install -r requirements.txt
```

### 2. PDF desteği için Poppler kur (isteğe bağlı)

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt install poppler-utils
```

### 3. API anahtarını ayarla

```bash
cp .env.example .env
# .env dosyasını aç ve ANTHROPIC_API_KEY değerini gir
```

### 4. Uygulamayı başlat

```bash
streamlit run app.py
```

---

## Proje Yapısı

```
ottoman_ocr/
├── app.py                      # Ana Streamlit uygulaması
├── config.py                   # API ayarları ve sistem promptu
├── requirements.txt
├── .env                        # API anahtarı (git'e ekleme!)
├── core/
│   ├── image_processor.py      # OpenCV/Pillow ön işleme
│   ├── ocr_engine.py           # Claude Vision API çağrıları
│   └── output_formatter.py     # .txt çıktı üretici
└── ui/
    ├── styles.py               # Özel CSS
    └── components.py           # Streamlit bileşenleri
```

---

## İleride: Offline (İnternet Gerektirmeyen) Kullanım

Kendi modelini eğittiğinde veya yerel bir model kullanmak istediğinde şu seçenekler mevcut:

| Seçenek | Açıklama | Zorluk |
|---|---|---|
| **Ollama + LLaVA** | Yerel vision modeli, kurulumu kolay | Kolay |
| **Ollama + LLaMA 3.2 Vision** | Daha güçlü, Meta'nın vision modeli | Kolay |
| **Fine-tuned model** | Kendi veri setiyle eğitilmiş model | Zor |
| **Tesseract (Arabic)** | Offline OCR, sadece matbu metin | Orta |

`ocr_engine.py` içindeki `analyze_image()` fonksiyonu değiştirilerek
herhangi bir backend'e (Ollama, yerel model, vb.) kolayca geçiş yapılabilir.
Diğer tüm modüller (görüntü işleme, UI, formatter) değişmez.
