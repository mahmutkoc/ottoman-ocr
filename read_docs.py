import zipfile, re, sys

files = [
    r"C:\Users\user\Downloads\ML.EEM 83-100-2 transkripsiyon.docx",
    r"C:\Users\user\Downloads\duit 9316 transkriptt.docx",
    r"C:\Users\user\Downloads\ferman transkript duzenlenmis.docx",
]

for f in files:
    print(f"\n{'='*60}")
    print(f"DOSYA: {f}")
    print('='*60)
    try:
        with zipfile.ZipFile(f) as z:
            xml = z.read('word/document.xml').decode('utf-8')
        # Paragraf sonlarını newline yap
        xml = re.sub(r'</w:p>', '\n', xml)
        # Tüm tag'leri sil
        xml = re.sub(r'<[^>]+>', '', xml)
        # Boşlukları temizle
        lines = [l.strip() for l in xml.split('\n') if l.strip()]
        print('\n'.join(lines[:100]))
    except Exception as e:
        print(f"HATA: {e}")
