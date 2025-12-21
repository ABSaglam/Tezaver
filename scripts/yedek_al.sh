#!/bin/bash

# Tezaver Mac UI Odaklı Yedekleme Scripti (Format: UI_Gün_Ay_Yıl_Saat_Dakika.zip)
# Kullanım: ./scripts/yedek_al.sh

PROJECT_ROOT="/Users/alisaglam/TezaverMac"
BACKUP_BASE="/Users/alisaglam/yedek/ui"

# Tarih bileşenlerini al
DAY=$(date +%d)
MONTH_NUM=$(date +%m)
YEAR=$(date +%Y)
HOUR=$(date +%H)
MINUTE=$(date +%M)

# Ay ismini Türkçe'ye çevir
case $MONTH_NUM in
    01) MONTH="Ocak" ;;
    02) MONTH="Şubat" ;;
    03) MONTH="Mart" ;;
    04) MONTH="Nisan" ;;
    05) MONTH="Mayıs" ;;
    06) MONTH="Haziran" ;;
    07) MONTH="Temmuz" ;;
    08) MONTH="Ağustos" ;;
    09) MONTH="Eylül" ;;
    10) MONTH="Ekim" ;;
    11) MONTH="Kasım" ;;
    12) MONTH="Aralık" ;;
esac

# Klasör ve Dosya İsmi: UI_17_Aralık_2025_Saat_12_44
BACKUP_NAME="UI_${DAY}_${MONTH}_${YEAR}_Saat_${HOUR}_${MINUTE}"
TEMP_DIR="/tmp/$BACKUP_NAME"
ZIP_FILE="$BACKUP_BASE/$BACKUP_NAME.zip"

echo "📂 UI Yedeklemesi başlatılıyor ($BACKUP_NAME)..."
mkdir -p "$TEMP_DIR"

# Sadece UI ile ilgili kısımları kopyala (src/tezaver/ui)
if [ -d "$PROJECT_ROOT/src/tezaver/ui" ]; then
    cp -r "$PROJECT_ROOT/src/tezaver/ui" "$TEMP_DIR/"
    echo "✅ UI kaynak kodları kopyalandı."
else
    echo "⚠️ UI klasörü bulunamadı: $PROJECT_ROOT/src/tezaver/ui"
fi

# Eğer data içinde UI ayarları varsa onları da ekle
if [ -f "$PROJECT_ROOT/data/user_settings.json" ]; then
    cp "$PROJECT_ROOT/data/user_settings.json" "$TEMP_DIR/"
    echo "✅ Kullanıcı ayarları kopyalandı."
fi

# Zip paketi oluştur
echo "📦 Paketleme yapılıyor..."
cd /tmp && zip -r "$ZIP_FILE" "$BACKUP_NAME" > /dev/null

# Temizlik
rm -rf "$TEMP_DIR"

echo "✅ UI yedeği başarıyla oluşturuldu: $ZIP_FILE"
ls -lh "$ZIP_FILE"


