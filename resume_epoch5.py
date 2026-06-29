"""
Epoch 5'i checkpoint'ten devam ettiren script.
checkpoints/epoch_4 modelini yükler, 1 epoch daha eğitir.
"""

import sys
import math
import time
import logging
import warnings
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import GradScaler, autocast
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from tqdm import tqdm

warnings.filterwarnings("ignore", category=UserWarning)

# Ana scriptten Config, Dataset, train_one_epoch, evaluate, cer fonksiyonlarını al
from trocr_finetune import Config, OttomanOCRDataset, evaluate, cer, set_seed, check_gpu, setup_logging


def train_one_epoch_resume(model, loader, optimizer, scheduler, scaler, device, cfg, logger):
    model.train()
    total_loss = 0.0
    optimizer.zero_grad()

    pbar = tqdm(loader, desc="Epoch 5 [Train]", leave=True)
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
            optimizer.zero_grad()
            scheduler.step()

        total_loss += loss.item() * cfg.GRAD_ACCUM

        if (step + 1) % cfg.LOG_EVERY_N == 0:
            lr_now = scheduler.get_last_lr()[0]
            logger.info(
                f"  Epoch 5 | Step {step+1}/{len(loader)} | "
                f"Loss: {total_loss/(step+1):.4f} | LR: {lr_now:.2e}"
            )
        pbar.set_postfix({"loss": f"{total_loss/(step+1):.4f}"})

    return total_loss / len(loader)


def main():
    cfg    = Config()
    logger = setup_logging(cfg.LOG_FILE)
    set_seed(cfg.SEED)
    device = check_gpu(logger)

    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # Veriyi yükle (aynı seed ile aynı bölünme olacak)
    df = pd.read_excel(cfg.XLSX_FILE)
    df = df.dropna(subset=[cfg.FILENAME_COL]).reset_index(drop=True)

    n       = len(df)
    n_train = int(n * cfg.TRAIN_RATIO)
    n_val   = int(n * cfg.VAL_RATIO)

    df_shuffled = df.sample(frac=1, random_state=cfg.SEED).reset_index(drop=True)
    df_train = df_shuffled.iloc[:n_train]
    df_val   = df_shuffled.iloc[n_train:n_train + n_val]
    df_test  = df_shuffled.iloc[n_train + n_val:]

    logger.info(f"Train: {len(df_train)}  |  Val: {len(df_val)}  |  Test: {len(df_test)}")

    # Epoch 4 checkpoint'inden yükle
    ckpt_path = cfg.CHECKPOINT_DIR / "epoch_4"
    logger.info(f"Checkpoint yükleniyor: {ckpt_path}")
    processor = TrOCRProcessor.from_pretrained(ckpt_path)
    model     = VisionEncoderDecoderModel.from_pretrained(ckpt_path).to(device)
    logger.info("Checkpoint yüklendi, Epoch 5 başlıyor...")

    train_ds = OttomanOCRDataset(df_train, cfg.IMAGE_DIR, processor, cfg.MAX_TARGET_LEN, cfg.IMG_SIZE, augment=True)
    val_ds   = OttomanOCRDataset(df_val,   cfg.IMAGE_DIR, processor, cfg.MAX_TARGET_LEN, cfg.IMG_SIZE, augment=False)
    test_ds  = OttomanOCRDataset(df_test,  cfg.IMAGE_DIR, processor, cfg.MAX_TARGET_LEN, cfg.IMG_SIZE, augment=False)

    train_loader = DataLoader(train_ds, batch_size=cfg.BATCH_SIZE, shuffle=True,  num_workers=0, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=cfg.BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=cfg.BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True)

    # OneCycleLR yerine basit CosineAnnealingLR — off-by-one sorunu yok
    optimizer = AdamW(model.parameters(), lr=cfg.LEARNING_RATE * 0.1, weight_decay=0.01)
    scheduler = CosineAnnealingLR(optimizer, T_max=len(train_loader), eta_min=1e-8)
    scaler    = GradScaler(enabled=cfg.FP16)

    epoch_start = time.time()
    train_loss  = train_one_epoch_resume(model, train_loader, optimizer, scheduler, scaler, device, cfg, logger)
    val_loss, val_cer = evaluate(model, val_loader, processor, device, cfg, logger, "Val")
    epoch_time  = time.time() - epoch_start

    logger.info(
        f"Epoch 5/5 tamamlandı | Train Loss: {train_loss:.4f} | "
        f"Val Loss: {val_loss:.4f} | Val CER: {val_cer:.2f}% | Süre: {epoch_time/60:.1f}dk"
    )

    # Checkpoint ve best model kaydet
    ckpt5 = cfg.CHECKPOINT_DIR / "epoch_5"
    model.save_pretrained(ckpt5)
    processor.save_pretrained(ckpt5)
    logger.info(f"Checkpoint kaydedildi: {ckpt5}")

    # Epoch 4 val loss ile karşılaştır
    prev_best = 2.2874
    if val_loss < prev_best:
        best_path = cfg.OUTPUT_DIR / "best_model"
        model.save_pretrained(best_path)
        processor.save_pretrained(best_path)
        logger.info(f"✓ En iyi model güncellendi! Val Loss: {val_loss:.4f} (önceki: {prev_best:.4f})")
    else:
        logger.info(f"Val Loss {val_loss:.4f} > {prev_best:.4f} — best_model güncellenmedi (epoch_4 daha iyi)")

    # Test değerlendirmesi
    logger.info("Test seti değerlendiriliyor...")
    test_loss, test_cer = evaluate(model, test_loader, processor, device, cfg, logger, "Test")

    logger.info("=" * 60)
    logger.info("EĞİTİM TAMAMLANDI (5/5 epoch)")
    logger.info(f"  Epoch 5 Val Loss : {val_loss:.4f}")
    logger.info(f"  Test Loss        : {test_loss:.4f}")
    logger.info(f"  Test CER         : {test_cer:.2f}%")
    logger.info(f"  Model dizini     : {cfg.OUTPUT_DIR / 'best_model'}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
