"""Osmanlıca Metin Okuyucu — Ana Uygulama."""

import streamlit as st

# Sayfa konfigürasyonu (en üstte olmalı)
st.set_page_config(
    page_title="Osmanlıca Metin Okuyucu",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.styles import CUSTOM_CSS
from ui.components import (
    render_header,
    render_preprocess_settings,
    render_image_preview,
    render_result,
    render_stats,
)
from core.image_processor import load_image, preprocess, image_to_base64
from core.ocr_engine import analyze_pages
from core.output_formatter import build_txt_content, get_download_filename

# CSS enjeksiyon
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def main():
    render_header()

    # Sidebar ayarları
    preprocess_opts = render_preprocess_settings()

    # ── Dosya Yükleme ──
    st.markdown('<div class="card-title">Belge Yükle</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        label="PNG, JPG veya PDF yükleyin",
        type=["png", "jpg", "jpeg", "pdf"],
        help="Tek veya çok sayfalı PDF desteklenmektedir.",
    )

    if uploaded is None:
        st.markdown(
            '<div class="card" style="text-align:center;color:#8a7a5a;padding:3rem;">'
            "Lütfen analiz etmek istediğiniz Osmanlıca belgeyi yükleyin.<br>"
            '<span style="font-size:2rem;">📜</span></div>',
            unsafe_allow_html=True,
        )
        return

    # ── Görüntüleri Yükle & Ön İşle ──
    file_bytes = uploaded.read()

    with st.spinner("Görüntü yükleniyor..."):
        try:
            pages = load_image(file_bytes, uploaded.name)
        except Exception as e:
            st.error(f"Dosya yüklenemedi: {e}")
            return

    processed_pages = []
    with st.spinner("Görüntü ön işleme uygulanıyor..."):
        for page in pages:
            proc = preprocess(page, **preprocess_opts)
            processed_pages.append(proc)

    st.success(f"{len(pages)} sayfa yüklendi ve işlendi.")

    # ── Görüntü Önizleme ──
    with st.expander("Görüntü Önizleme", expanded=True):
        for i, (orig, proc) in enumerate(zip(pages, processed_pages), start=1):
            render_image_preview(orig, proc, page_num=i)
            if i < len(pages):
                st.markdown("---")

    st.markdown("---")

    # ── Analiz Başlat ──
    if st.button("🔍  Metni Analiz Et", use_container_width=True):
        images_b64 = [image_to_base64(p) for p in processed_pages]

        page_results = []
        progress = st.progress(0, text="Analiz başlatılıyor...")

        for i, b64 in enumerate(images_b64, start=1):
            progress.progress(
                (i - 1) / len(images_b64),
                text=f"Sayfa {i} / {len(images_b64)} analiz ediliyor...",
            )
            with st.spinner(f"Sayfa {i} okunuyor..."):
                try:
                    from core.ocr_engine import analyze_image
                    result = analyze_image(b64, page_num=i, total_pages=len(images_b64))
                    page_results.append({"page": i, "result": result})
                except Exception as e:
                    page_results.append({"page": i, "result": f"HATA: {e}"})

        progress.progress(1.0, text="Analiz tamamlandı.")

        # Sonuçları session_state'e kaydet
        st.session_state["page_results"] = page_results
        st.session_state["filename"] = uploaded.name

    # ── Sonuçları Göster ──
    if "page_results" in st.session_state:
        page_results = st.session_state["page_results"]
        filename = st.session_state["filename"]

        st.markdown("---")
        st.markdown(
            '<div class="card-title">Analiz Sonuçları</div>',
            unsafe_allow_html=True,
        )

        render_stats(page_results)
        st.markdown("")

        for item in page_results:
            render_result(item["result"], item["page"], len(page_results))
            if item["page"] < len(page_results):
                st.markdown("---")

        # ── İndirme ──
        st.markdown("---")
        txt_content = build_txt_content(filename, page_results)
        dl_name = get_download_filename(filename)

        st.download_button(
            label="⬇  Sonucu .txt Olarak İndir",
            data=txt_content.encode("utf-8"),
            file_name=dl_name,
            mime="text/plain; charset=utf-8",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
