---
description: Projenin standart yedeğini alır
---

Bu workflow, UI klasörünü `/Users/alisaglam/yedek/UI` klasörüne tarih damgalı zip olarak yedekler.

1. `/yedek` veya "Yedek al" komutunu duyduğunda.
// turbo
2. UI yedeğini al:
```bash
#!/bin/bash
YEDEK_DIR="/Users/alisaglam/yedek/UI"
TIMESTAMP=$(date +"%d_%B_%Y_Saat_%H_%M" | sed 's/January/Ocak/;s/February/Şubat/;s/March/Mart/;s/April/Nisan/;s/May/Mayıs/;s/June/Haziran/;s/July/Temmuz/;s/August/Ağustos/;s/September/Eylül/;s/October/Ekim/;s/November/Kasım/;s/December/Aralık/')
BACKUP_FILE="${YEDEK_DIR}/UI_${TIMESTAMP}.zip"

cd /Users/alisaglam/TezaverMac/src/tezaver/ui
zip -r "$BACKUP_FILE" . -x "*.pyc" -x "__pycache__/*" -x ".DS_Store"

echo "✅ Yedek: $BACKUP_FILE"
ls -lh "$BACKUP_FILE" | awk '{print "📊 Boyut: " $5}'
```
