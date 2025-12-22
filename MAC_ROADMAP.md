# TEZAVER MAC — ROADMAP (Phase-Gated)

## Çalışma Protokolü (DEĞİŞMEZ)
- **Tek faz kuralı:** Aynı anda sadece 1 faz aktif.
- **Faz bitiş şartı:** Fazdaki tüm checkbox'lar ✅ + "Kabul Kriteri" + "Kanıt" sağlanmadan sonraki faza geçilmez.
- **Kanıt formatı:** (a) UI ekran görüntüsü veya açıklaması (b) oluşan dosya path'i (c) kısa log/komut çıktısı.
- **Kritik:** Faz 0'da kod değiştirmek yok. Sadece doğrula.

---

## Faz 0 — Ingest & Envanter Doğrulama (VERIFY ONLY)
> Amaç: Mevcut Ingest ve "envanter/browse" zaten var mı? Varsa dokunma.

- [ ] **MAC-0001 (VERIFY)** Output roots & manifest varlığı
  - UI Route: N/A
  - Kabul Kriteri:
    - `.tezaver_matrix/approved/*/manifest.json` bulunuyor olmalı (örnek var). 
    - `.tezaver_matrix/candidates/*/manifest.json` bulunuyor olmalı.
    - `out/matrix_candidates/*/*/bundle_v1/manifest.json` bulunuyor olmalı.
  - Kanıt: `ls` çıktısı + örnek manifest snippet (3 dosya).

- [ ] **MAC-0002 (VERIFY)** Envanter/Browser mevcut mu?
  - UI Route: `Time Labs` (`src/tezaver/ui/time_labs_tab.py`), `Fast15 Lab` (`src/tezaver/ui/fast15_lab_tab.py`)
  - Kabul Kriteri:
    - En az 1 coin için 15m/1h/4h event listesi görüntülenebiliyor (liste/tablolaşmış).
  - Kanıt: UI ekran açıklaması (neye tıklayınca ne görünüyor) + 1 örnek coin.

- [ ] **MAC-0003 (VERIFY)** Faz 0 Sonuç Raporu
  - Çıktı: `reports/PHASE0_VERIFY.md`
  - İçerik: "Var / Yok / Eksik" maddeleri + Faz 1'e başlamadan önce gereksiz dokunulmaması gereken dosyalar listesi.

---

## Faz 1 — ONY v1 (Somut Onay Süreci: Gör → İşaretle → Kaydet → Onayla)
> Amaç: Onay süreci gözle görülür şekilde çalışsın.

- [ ] **MAC-1001** ONY Studio grafiği + marker'lar
  - UI Route: `Sniper Studio` (`src/tezaver/ui/chart_area.py`)
  - Kabul Kriteri:
    - Grafik 4 panel çiziliyor.
    - Entry marker ve opsiyonel Exit marker görünüyor.
  - Kanıt: 1 event üzerinde marker'lı görünüm.
  - Referans: `render_sniper_studio_chart(... entry_offset, exit_offset)` mevcut.

- [ ] **MAC-1002** Entry/Exit işaretleme kontrolü (offset)
  - UI Route: Sniper Studio
  - Kabul Kriteri:
    - entry_bar_offset değişince marker yeri değişiyor.
    - exit_bar_offset opsiyonel; girilince exit marker çıkıyor.
  - Referans: Annotation modeli offset tabanlı.

- [ ] **MAC-1003** ONY storage (kayıt)
  - UI Route: Sniper Studio → "Save"
  - Kabul Kriteri:
    - `data/sniper/{SYMBOL}/{TIMEFRAME}/sniper_annotations_v1.json` dosyasına yazıyor.
  - Kanıt: dosya içinden 1 kayıt snippet.

- [ ] **MAC-1004** ONY workflow: PENDING → APPROVED / REJECTED
  - UI Route: Sniper Studio + "ONY Queue" (varsa mevcut sayfaya ek)
  - Kabul Kriteri:
    - status alanı PENDING/APPROVED/REJECTED akıyor.
  - Referans: status/label alanları mevcut (`SniperAnnotation.status`).

- [ ] **MAC-1005** Faz 1 Kanıt Paketi
  - Çıktı: `reports/PHASE1_ONY_PROOF.md`
  - İçerik: 1 event için "işaretle→kaydet→onayla" adımları + dosya path + snippet.

---

## Faz 2 — Normalize v1 (Auto-snap + Standardizasyon)
> Amaç: "Ben sadece onaylıyordum" modunu geri getirmek: snap_reason/snap_distance üret.

- [ ] **MAC-2001** NormalizeEngine v1: snap_reason + snap_distance_bars + confidence + algo_version
  - UI Route: Sniper Studio (Onay öncesi görünür)
  - Kabul Kriteri: UI'de snap metadatası görünür, JSON'a yazılır.
  - Gap: snap_reason/snap_distance şu an hesaplanmıyor.

- [ ] **MAC-2002** Offset → timestamp çözümü
  - Kabul Kriteri: approved_entry_ts/approved_exit_ts hesaplanır ve saklanır (exit opsiyonel).
  - Gap: "Timestamp yok, offset'ten hesaplanır" maddesi.

- [ ] **MAC-2003** Faz 2 Kanıt
  - Çıktı: `reports/PHASE2_NORMALIZE_PROOF.md`

---

## Faz 3 — Dökümhane v1 (QC + Blend + Packaging + Publish)
> Amaç: Onaylı event → mühürlü ürün.

- [ ] **MAC-3001** QC Gate v1 (PASS/WARN/FAIL + skor/ihlaller)
  - Kabul Kriteri: `qc_report_v1.json` üretilir; FAIL publish'i durdurur.

- [ ] **MAC-3002** Blend v1 (15m/1h/4h uyum/çelişki)
  - Kabul Kriteri: `blend_report_v1.json` üretilir.

- [ ] **MAC-3003** Packaging v1: `approved_bundle_v1.json` üretimi
  - Kabul Kriteri:
    - approved manifest bugün entry/exit taşımıyor; bu bundle dolduracak.
    - Bundle içine: entry/exit (offset+ts), grade, trace (engine_version/data_fingerprint/config_signature) girecek.
  - Gap: Gap listesi bu alanları "GEREKLİ" diyor.
  - Kaynak: bundle trace ham maddesi `out/matrix_candidates/.../bundle_v1/manifest.json` içinde var.

- [ ] **MAC-3004** Publish policy (Mac publish)
  - Kabul Kriteri: PASS/WARN publish eder, FAIL etmez.

- [ ] **MAC-3005** Faz 3 Kanıt
  - Çıktı: `reports/PHASE3_FOUNDRY_PROOF.md`

---

## Faz 4 — Feedback Loop (Sniper/WAR/LIVE outcome → Dökümhane iyileştirme)
- [ ] **MAC-4001** Outcome importer
- [ ] **MAC-4002** Calibration (grade/snap/qc eşikleri)
- [ ] **MAC-4003** Faz 4 Kanıt: `reports/PHASE4_FEEDBACK_PROOF.md`

---

## "Şimdi ne yapıyoruz?" (RUNBOOK)
1) Faz 0 (VERIFY) → `PHASE0_VERIFY.md` üret → kullanıcı onayı
2) Faz 1 (ONY) → `PHASE1_ONY_PROOF.md` → kullanıcı onayı
3) Faz 2 (Normalize) → `PHASE2_NORMALIZE_PROOF.md` → kullanıcı onayı
4) Faz 3 (Dökümhane) → `PHASE3_FOUNDRY_PROOF.md` → kullanıcı onayı
5) Faz 4 (Feedback) → `PHASE4_FEEDBACK_PROOF.md` → kullanıcı onayı

---

## Referans Dokümanlar
- `docs/FOUNDATION_AUTO_SNAP_MAP.md` — Auto-snap + ONY arkeolojisi
- `reports/MAC_ARCHAEOLOGY_REPORT.md` — Pipeline modül listesi
- `reports/MAC_ONY_CONTRACT_REPORT.md` — ONY kontrat detayları
