"""Sonuç metni formatla ve indirilebilir .txt üret."""

from datetime import datetime


def build_txt_content(filename: str, page_results: list[dict]) -> str:
    """İndirme için düzenli .txt içeriği oluştur."""
    lines = []
    lines.append("=" * 70)
    lines.append("OSMANLıCA METİN ANALİZ RAPORU")
    lines.append("=" * 70)
    lines.append(f"Dosya     : {filename}")
    lines.append(f"Tarih     : {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append(f"Sayfa say.: {len(page_results)}")
    lines.append("=" * 70)
    lines.append("")

    for item in page_results:
        if len(page_results) > 1:
            lines.append(f"{'─' * 30}  SAYFA {item['page']}  {'─' * 30}")
            lines.append("")
        lines.append(item["result"])
        lines.append("")

    lines.append("=" * 70)
    lines.append("Bu rapor Osmanlıca OCR Uygulaması tarafından oluşturulmuştur.")
    lines.append("=" * 70)

    return "\n".join(lines)


def get_download_filename(original_filename: str) -> str:
    """İndirme için dosya adı üret."""
    stem = original_filename.rsplit(".", 1)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_osmanlica_{timestamp}.txt"
