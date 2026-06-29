"""Osmanlıca Metin Okuyucu — Ana Uygulama."""

import os

import streamlit as st

st.set_page_config(
    page_title="Osmanlıca Metin Okuyucu",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _dogru_sifreyi_al() -> str | None:
    """Şifreyi Streamlit secrets veya ortam değişkeninden oku."""
    try:
        if "APP_PASSWORD" in st.secrets:
            return st.secrets["APP_PASSWORD"]
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD")


def giris_kontrolu() -> bool:
    """
    Şifre korumalı giriş ekranı. APP_PASSWORD tanımlı değilse
    (örn. yerel geliştirme ortamında) kontrol atlanır.
    """
    dogru_sifre = _dogru_sifreyi_al()
    if not dogru_sifre:
        return True

    if st.session_state.get("girildi"):
        return True

    st.markdown(
        "<div style='max-width:400px;margin:6rem auto;text-align:center;'>"
        "<h2>🔒 Osmanlıca Metin Okuyucu</h2>"
        "<p>Devam etmek için şifre girin.</p></div>",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        sifre = st.text_input("Şifre", type="password", key="sifre_giris")
        if st.button("Giriş Yap", use_container_width=True):
            if sifre == dogru_sifre:
                st.session_state["girildi"] = True
                st.rerun()
            else:
                st.error("Hatalı şifre.")
    return False


if not giris_kontrolu():
    st.stop()

from ui.styles import CUSTOM_CSS
from ui.components import (
    render_header,
    render_preprocess_settings,
    render_image_preview,
    render_result,
    render_stats,
)
from core.image_processor import load_image, preprocess, image_to_base64
from core.ocr_engine import analyze_image as analyze_image_claude
from core.pipeline import analyze_image_pipeline, pipeline_hazir_mi
from core.output_formatter import build_txt_content, get_download_filename
from core.dataset_manager import kaydet, istatistik_getir

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

BELGE_TURLERI = ["ferman", "mektup", "senet", "berat", "sicil", "arzuhal", "diger"]
HAT_STILLERI  = ["nesih", "rika", "talik", "divani", "matbu"]


def veri_seti_paneli():
    """Sidebar'da veri seti istatistiklerini göster."""
    ist = istatistik_getir()
    toplam = ist["toplam_belge"]
    hedef  = ist["hedef"]
    yuzde  = int(toplam / hedef * 100) if hedef else 0

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<p style="color:#c9a84c;font-size:0.8rem;text-transform:uppercase;'
        'letter-spacing:0.1em;margin-bottom:0.5rem;">Veri Seti</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.progress(toplam / hedef if hedef else 0)
    st.sidebar.markdown(
        f'<p style="color:#d4c5a0;font-size:0.82rem;">'
        f'<b>{toplam}</b> / {hedef} belge &nbsp;·&nbsp; %{yuzde}</p>',
        unsafe_allow_html=True,
    )


def onay_paneli(file_bytes: bytes, filename: str, page_results: list):
    """Analiz sonrası onay ve veri setine kaydetme paneli."""
    st.markdown("---")
    st.markdown(
        '<div class="card-title">Veri Setine Ekle</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#8a7a5a;font-size:0.85rem;margin-bottom:1rem;">'
        "Claude'un okuması doğru mu? Onaylarsanız bu belge veri setinize kaydedilir "
        "ve ilerideki kendi modelinizi eğitmekte kullanılır.</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        belge_turu = st.selectbox("Belge Türü", BELGE_TURLERI, index=6)
    with col2:
        hat_stili = st.selectbox("Hat Stili", HAT_STILLERI, index=0)

    col_onayla, col_reddet = st.columns(2)

    with col_onayla:
        if st.button("✅  Onayla ve Kaydet", use_container_width=True):
            birlesik_analiz = "\n\n".join(
                f"[Sayfa {r['page']}]\n{r['result']}" for r in page_results
            )
            try:
                yeni_id = kaydet(
                    goruntu_bytes=file_bytes,
                    dosya_adi=filename,
                    analiz_sonucu=birlesik_analiz,
                    belge_turu=belge_turu,
                    hat_stili=hat_stili,
                )
                st.success(f"✅ Belge #{yeni_id} veri setine kaydedildi!")
                st.session_state["kaydedildi"] = True
                st.rerun()
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")

    with col_reddet:
        if st.button("❌  Reddet", use_container_width=True):
            st.warning("Belge reddedildi, veri setine eklenmedi.")
            st.session_state["kaydedildi"] = False


def main():
    render_header()
    preprocess_opts = render_preprocess_settings()
    veri_seti_paneli()

    # ── OCR Motor Seçimi ──
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<p style="color:#c9a84c;font-size:0.8rem;text-transform:uppercase;'
        'letter-spacing:0.1em;margin-bottom:0.5rem;">OCR Motoru</p>',
        unsafe_allow_html=True,
    )
    motor_secenekler = []
    if pipeline_hazir_mi():
        motor_secenekler.append("🕌 PaddleOCR + Transliterasyon (Offline)")
    motor_secenekler.append("☁️ Claude API")
    secilen_motor = st.sidebar.radio("Motor", motor_secenekler, index=0)

    if secilen_motor.startswith("🕌"):
        st.sidebar.success("Offline pipeline hazır ✓")
        arapca_goster = st.sidebar.checkbox("Ara sonucu göster (Arap harfleri)", value=True)
    else:
        arapca_goster = False
        if secilen_motor.startswith("🤖"):
            st.sidebar.success("Fine-tune model hazır ✓")
        else:
            st.sidebar.info("Claude Vision API kullanılıyor")

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
                    if secilen_motor.startswith("🕌"):
                        result = analyze_image_pipeline(b64, page_num=i, total_pages=len(images_b64), arapca_da_goster=arapca_goster)
                    else:
                        result = analyze_image_claude(b64, page_num=i, total_pages=len(images_b64))
                    page_results.append({"page": i, "result": result})
                except Exception as e:
                    page_results.append({"page": i, "result": f"HATA: {e}"})

        progress.progress(1.0, text="Analiz tamamlandı.")
        st.session_state["page_results"] = page_results
        st.session_state["filename"] = uploaded.name
        st.session_state["file_bytes"] = file_bytes
        st.session_state.pop("kaydedildi", None)

    # ── Sonuçları Göster ──
    if "page_results" in st.session_state:
        page_results = st.session_state["page_results"]
        filename     = st.session_state["filename"]
        file_bytes_s = st.session_state.get("file_bytes", file_bytes)

        st.markdown("---")
        st.markdown('<div class="card-title">Analiz Sonuçları</div>', unsafe_allow_html=True)

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

        # ── Onay Paneli ──
        if not st.session_state.get("kaydedildi"):
            onay_paneli(file_bytes_s, filename, page_results)
        else:
            st.success("✅ Bu belge zaten veri setine kaydedildi.")


if __name__ == "__main__":
    main()
