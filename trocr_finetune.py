"""
Osmanlıca TrOCR Fine-Tuning Scripti
=====================================
Model  : microsoft/trocr-large-handwritten
GPU    : RTX 4070 Ti Super (16 GB VRAM)
LR     : 5e-5
Batch  : 8
Epochs : 5
Veri   : C:\\Users\\user\\ottoman-ocr\\
"""

import os
import sys
import time
import logging
import warnings
from pathlib import Path

import pandas as pd
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader, random_split
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from torch.cuda.amp import GradScaler, autocast
from transformers import (
    TrOCRProcessor,
    VisionEncoderDecoderModel,
    default_data_collator,
)
from tqdm import tqdm

warnings.filterwarnings("ignore", category=UserWarning)

# ─────────────────────────────────────────────
# 1. KONFİGÜRASYON
# ─────────────────────────────────────────────
class Config:
    # Klasör / dosya yolları
    DATA_DIR        = Path(r"C:\Users\user\ottoman-ocr")
    XLSX_FILE       = DATA_DIR / "osmanli_transkripsiyon.xlsx"
    OUTPUT_DIR      = DATA_DIR / "model_output"
    LOG_FILE        = DATA_DIR / "training.log"
    CHECKPOINT_DIR  = DATA_DIR / "checkpoints"

    # xlsx sütun adları
    FILENAME_COL    = "file_name"
    TEXT_COL        = "text"

    # PNG'lerin bulunduğu klasör (xlsx'teki dosya adları burada aranır)
    IMAGE_DIR       = DATA_DIR / "egitim verileri-20260603T164853Z-3-001" / "egitim verileri"

    # Model
    BASE_MODEL      = "microsoft/trocr-large-handwritten"

    # Eğitim hiperparametreleri
    LEARNING_RATE   = 5e-5
    BATCH_SIZE      = 8
    NUM_EPOCHS      = 5
    MAX_TARGET_LEN  = 128          # token cinsinden maks transkripsiyon uzunluğu
    IMG_SIZE        = (384, 384)   # TrOCR-large'ın beklediği boyut

    # Veri bölünmesi
    TRAIN_RATIO     = 0.85
    VAL_RATIO       = 0.10
    TEST_RATIO      = 0.05         # geriye kalan

    # Mixed precision & optimizasyon
    FP16            = True         # RTX 4070 Ti Super için önerilir
    GRAD_ACCUM      = 2            # efektif batch = 8 × 2 = 16
    MAX_GRAD_NORM   = 1.0
    WARMUP_PCT      = 0.1          # OneCycleLR warmup oranı

    # Loglama
    LOG_EVERY_N     = 50           # adım başına log sıklığı
    SAVE_EVERY_N    = 1            # epoch başına checkpoint kaydetme

    # Tekrarlanabilirlik
    SEED            = 42


# ─────────────────────────────────────────────
# 2. YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────
def setup_logging(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def set_seed(seed: int):
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def check_gpu(logger: logging.Logger) -> torch.device:
    if not torch.cuda.is_available():
        logger.warning("CUDA bulunamadı! CPU ile devam ediliyor (çok yavaş olacak).")
        return torch.device("cpu")
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb  = torch.cuda.get_device_properties(0).total_memory / 1e9
    logger.info(f"GPU: {gpu_name}  |  VRAM: {vram_gb:.1f} GB")
    return torch.device("cuda")


def cer(pred: str, target: str) -> float:
    if len(target) == 0:
        return 0.0 if len(pred) == 0 else 1.0
    try:
        from rapidfuzz.distance import Levenshtein
        return Levenshtein.distance(pred, target) / len(target)
    except ImportError:
        return float("nan")


# ─────────────────────────────────────────────
# 3. VERİ SETİ
# ─────────────────────────────────────────────
class OttomanOCRDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        data_dir: Path,
        processor: TrOCRProcessor,
        max_target_len: int,
        img_size: tuple,
        augment: bool = False,
    ):
        self.df            = df.reset_index(drop=True)
        self.data_dir      = data_dir
        self.processor     = processor
        self.max_target_len = max_target_len
        self.img_size      = img_size
        self.augment       = augment

        # Opsiyonel: eğitim için hafif augmentation
        if augment:
            try:
                from torchvision import transforms
                self.aug = transforms.Compose([
                    transforms.RandomRotation(degrees=2),
                    transforms.RandomAffine(degrees=0, translate=(0.02, 0.02)),
                    transforms.ColorJitter(brightness=0.2, contrast=0.2),
                ])
            except ImportError:
                self.aug = None
        else:
            self.aug = None

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row      = self.df.iloc[idx]
        filename = str(row[Config.FILENAME_COL])
        text     = str(row[Config.TEXT_COL]) if pd.notna(row[Config.TEXT_COL]) else ""

        # Dosya adında uzantı yoksa .png ekle
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".tiff")):
            filename += ".png"

        img_path = self.data_dir / filename
        try:
            image = Image.open(img_path).convert("RGB")
            image = image.resize(self.img_size, Image.LANCZOS)
        except (FileNotFoundError, OSError):
            # Bozuk/eksik görsel → siyah kare ile devam et
            image = Image.new("RGB", self.img_size, color=(0, 0, 0))

        if self.aug is not None:
            image = self.aug(image)

        pixel_values = self.processor(
            images=image, return_tensors="pt"
        ).pixel_values.squeeze(0)

        labels = self.processor.tokenizer(
            text,
            padding="max_length",
            max_length=self.max_target_len,
            truncation=True,
            return_tensors="pt",
        ).input_ids.squeeze(0)

        # Padding token'ları -100'e çevir (loss hesaplanmasın)
        labels[labels == self.processor.tokenizer.pad_token_id] = -100

        return {"pixel_values": pixel_values, "labels": labels}


# ─────────────────────────────────────────────
# 4. EĞİTİM & DEĞERLENDİRME DÖNGÜLERI
# ─────────────────────────────────────────────
def train_one_epoch(
    model, loader, optimizer, scheduler, scaler, device, cfg, logger, epoch
):
    model.train()
    total_loss   = 0.0
    total_steps  = 0
    start_time   = time.time()

    pbar = tqdm(loader, desc=f"Epoch {epoch+1}/{cfg.NUM_EPOCHS} [Train]", leave=False)

    optimizer.zero_grad()
    for step, batch in enumerate(pbar):
        pixel_values = batch["pixel_values"].to(device)
        labels       = batch["labels"].to(device)

        with autocast(enabled=cfg.FP16):
            outputs = model(pixel_values=pixel_values, labels=labels)
            loss    = outputs.loss / cfg.GRAD_ACCUM

        scaler.scale(loss).backward()

        if (step + 1) % cfg.GRAD_ACCUM == 0 or (step + 1) == len(loader):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.MAX_GRAD_NORM)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            optimizer.zero_grad()

        total_loss  += outputs.loss.item()
        total_steps += 1

        pbar.set_postfix({"loss": f"{total_loss/total_steps:.4f}"})

        if (step + 1) % cfg.LOG_EVERY_N == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Epoch {epoch+1} | Step {step+1}/{len(loader)} | "
                f"Loss: {total_loss/total_steps:.4f} | "
                f"LR: {scheduler.get_last_lr()[0]:.2e} | "
                f"Elapsed: {elapsed:.0f}s"
            )

    return total_loss / total_steps


@torch.no_grad()
def evaluate(model, loader, processor, device, cfg, logger, split_name="Val"):
    model.eval()
    total_loss = 0.0
    total_cer  = 0.0
    n_samples  = 0

    try:
        import editdistance  # CER için
        compute_cer = True
    except ImportError:
        compute_cer = False

    pbar = tqdm(loader, desc=f"  [{split_name}]", leave=False)
    for batch in pbar:
        pixel_values = batch["pixel_values"].to(device)
        labels       = batch["labels"].to(device)

        with autocast(enabled=cfg.FP16):
            outputs = model(pixel_values=pixel_values, labels=labels)
        total_loss += outputs.loss.item()

        if compute_cer:
            generated = model.generate(
                pixel_values,
                max_new_tokens=cfg.MAX_TARGET_LEN,
            )
            preds   = processor.batch_decode(generated, skip_special_tokens=True)
            # label'lardaki -100'leri pad ile değiştir
            clean_labels = labels.clone()
            clean_labels[clean_labels == -100] = processor.tokenizer.pad_token_id
            targets = processor.batch_decode(clean_labels, skip_special_tokens=True)

            for p, t in zip(preds, targets):
                total_cer += cer(p, t)
                n_samples += 1

        pbar.set_postfix({"loss": f"{total_loss/len(loader):.4f}"})

    avg_loss = total_loss / len(loader)
    avg_cer  = (total_cer / n_samples * 100) if n_samples > 0 else float("nan")
    logger.info(f"  {split_name} Loss: {avg_loss:.4f} | CER: {avg_cer:.2f}%")
    return avg_loss, avg_cer


# ─────────────────────────────────────────────
# 5. ANA FONKSİYON
# ─────────────────────────────────────────────
def main():
    cfg    = Config()
    logger = setup_logging(cfg.LOG_FILE)
    set_seed(cfg.SEED)
    device = check_gpu(logger)

    # Çıktı klasörlerini oluştur
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Veriyi yükle ──────────────────────────
    logger.info(f"xlsx okunuyor: {cfg.XLSX_FILE}")
    df = pd.read_excel(cfg.XLSX_FILE)
    logger.info(f"Toplam satır: {len(df)}  |  Sütunlar: {list(df.columns)}")

    # Sütun adlarını kontrol et
    for col in [cfg.FILENAME_COL, cfg.TEXT_COL]:
        if col not in df.columns:
            logger.error(
                f"'{col}' sütunu bulunamadı. "
                f"Mevcut sütunlar: {list(df.columns)}\n"
                f"Config'deki FILENAME_COL / TEXT_COL değerlerini güncelleyin."
            )
            sys.exit(1)

    df = df.dropna(subset=[cfg.FILENAME_COL]).reset_index(drop=True)
    logger.info(f"Geçerli satır (filename dolu): {len(df)}")

    # ── Train / Val / Test bölünmesi ──────────
    n       = len(df)
    n_train = int(n * cfg.TRAIN_RATIO)
    n_val   = int(n * cfg.VAL_RATIO)
    n_test  = n - n_train - n_val

    df_shuffled = df.sample(frac=1, random_state=cfg.SEED).reset_index(drop=True)
    df_train = df_shuffled.iloc[:n_train]
    df_val   = df_shuffled.iloc[n_train:n_train + n_val]
    df_test  = df_shuffled.iloc[n_train + n_val:]

    logger.info(f"Train: {len(df_train)}  |  Val: {len(df_val)}  |  Test: {len(df_test)}")

    # ── Processor & Model ─────────────────────
    logger.info(f"Model yükleniyor: {cfg.BASE_MODEL} …")
    processor = TrOCRProcessor.from_pretrained(cfg.BASE_MODEL)
    model     = VisionEncoderDecoderModel.from_pretrained(cfg.BASE_MODEL)

    # Decoder token ayarları
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    model.config.pad_token_id           = processor.tokenizer.pad_token_id
    model.config.eos_token_id           = processor.tokenizer.sep_token_id
    model.config.vocab_size             = model.config.decoder.vocab_size
    model.config.max_length             = cfg.MAX_TARGET_LEN
    model.config.early_stopping         = True
    model.config.no_repeat_ngram_size   = 3
    model.config.length_penalty         = 2.0
    model.config.num_beams              = 4

    model = model.to(device)
    total_params = sum(p.numel() for p in model.parameters()) / 1e6
    logger.info(f"Model parametresi: {total_params:.1f}M")

    # ── Dataset & DataLoader ──────────────────
    train_ds = OttomanOCRDataset(
        df_train, cfg.IMAGE_DIR, processor,
        cfg.MAX_TARGET_LEN, cfg.IMG_SIZE, augment=True
    )
    val_ds = OttomanOCRDataset(
        df_val, cfg.IMAGE_DIR, processor,
        cfg.MAX_TARGET_LEN, cfg.IMG_SIZE, augment=False
    )
    test_ds = OttomanOCRDataset(
        df_test, cfg.IMAGE_DIR, processor,
        cfg.MAX_TARGET_LEN, cfg.IMG_SIZE, augment=False
    )

    train_loader = DataLoader(
        train_ds, batch_size=cfg.BATCH_SIZE,
        shuffle=True, num_workers=4, pin_memory=True
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg.BATCH_SIZE,
        shuffle=False, num_workers=4, pin_memory=True
    )
    test_loader = DataLoader(
        test_ds, batch_size=cfg.BATCH_SIZE,
        shuffle=False, num_workers=4, pin_memory=True
    )

    # ── Optimizer & Scheduler ─────────────────
    optimizer = AdamW(model.parameters(), lr=cfg.LEARNING_RATE, weight_decay=0.01)
    total_steps = (len(train_loader) // cfg.GRAD_ACCUM) * cfg.NUM_EPOCHS
    scheduler = OneCycleLR(
        optimizer,
        max_lr=cfg.LEARNING_RATE,
        total_steps=total_steps,
        pct_start=cfg.WARMUP_PCT,
        anneal_strategy="cos",
    )
    scaler = GradScaler(enabled=cfg.FP16)

    # ── Eğitim döngüsü ───────────────────────
    logger.info("=" * 60)
    logger.info("EĞİTİM BAŞLIYOR")
    logger.info(f"  LR={cfg.LEARNING_RATE} | Batch={cfg.BATCH_SIZE} | "
                f"Epochs={cfg.NUM_EPOCHS} | FP16={cfg.FP16}")
    logger.info("=" * 60)

    best_val_loss = float("inf")
    history = []

    for epoch in range(cfg.NUM_EPOCHS):
        epoch_start = time.time()

        train_loss = train_one_epoch(
            model, train_loader, optimizer, scheduler,
            scaler, device, cfg, logger, epoch
        )
        val_loss, val_cer = evaluate(
            model, val_loader, processor, device, cfg, logger, "Val"
        )

        epoch_time = time.time() - epoch_start
        logger.info(
            f"Epoch {epoch+1}/{cfg.NUM_EPOCHS} tamamlandı | "
            f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
            f"Val CER: {val_cer:.2f}% | Süre: {epoch_time/60:.1f}dk"
        )
        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_cer": val_cer,
        })

        # Checkpoint kaydet
        if (epoch + 1) % cfg.SAVE_EVERY_N == 0:
            ckpt_path = cfg.CHECKPOINT_DIR / f"epoch_{epoch+1}"
            model.save_pretrained(ckpt_path)
            processor.save_pretrained(ckpt_path)
            logger.info(f"  Checkpoint kaydedildi: {ckpt_path}")

        # En iyi modeli kaydet
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_path = cfg.OUTPUT_DIR / "best_model"
            model.save_pretrained(best_path)
            processor.save_pretrained(best_path)
            logger.info(f"  ✓ En iyi model güncellendi (Val Loss: {best_val_loss:.4f})")

    # ── Test değerlendirmesi ──────────────────
    logger.info("Test seti değerlendiriliyor…")
    test_loss, test_cer = evaluate(
        model, test_loader, processor, device, cfg, logger, "Test"
    )

    # ── Eğitim geçmişini kaydet ───────────────
    hist_df = pd.DataFrame(history)
    hist_path = cfg.OUTPUT_DIR / "training_history.xlsx"
    hist_df.to_excel(hist_path, index=False)
    logger.info(f"Eğitim geçmişi kaydedildi: {hist_path}")

    # ── Final özet ───────────────────────────
    logger.info("=" * 60)
    logger.info("EĞİTİM TAMAMLANDI")
    logger.info(f"  En iyi Val Loss : {best_val_loss:.4f}")
    logger.info(f"  Test Loss       : {test_loss:.4f}")
    logger.info(f"  Test CER        : {test_cer:.2f}%")
    logger.info(f"  Model dizini    : {cfg.OUTPUT_DIR / 'best_model'}")
    logger.info("=" * 60)


# ─────────────────────────────────────────────
# 6. INFERENCE ÖRNEĞİ (isteğe bağlı)
# ─────────────────────────────────────────────
def predict_single(image_path: str, model_dir: str = None):
    """
    Tek bir görsel için transkripsiyon üretir.
    Kullanım:
        from trocr_finetune import predict_single
        text = predict_single(r"C:\\Users\\user\\ottoman-ocr\\ornek.png")
        print(text)
    """
    cfg = Config()
    if model_dir is None:
        model_dir = str(cfg.OUTPUT_DIR / "best_model")

    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = TrOCRProcessor.from_pretrained(model_dir)
    model     = VisionEncoderDecoderModel.from_pretrained(model_dir).to(device)
    model.eval()

    image        = Image.open(image_path).convert("RGB").resize(cfg.IMG_SIZE, Image.LANCZOS)
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)

    with torch.no_grad():
        ids = model.generate(pixel_values, max_new_tokens=cfg.MAX_TARGET_LEN)
    return processor.batch_decode(ids, skip_special_tokens=True)[0]


if __name__ == "__main__":
    main()
