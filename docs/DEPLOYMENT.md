# Tezaver-Mac Deployment Guide

📦 **Production Deployment Kılavuzu**

---

## 🎯 Sistem Gereksinimleri

### Donanım
- **CPU**: 2+ cores (4 cores önerilir)
- **RAM**: 4GB minimum (8GB önerilir)
- **Disk**: 10GB minimum (20GB önerilir)
- **Network**: Stabil internet bağlantısı (API çağrıları için)

### Yazılım
- **OS**: macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **Python**: 3.11 (önerilir), 3.9-3.13 arası desteklenir
- **Git**: Versiyon kontrolü için

---

## 🚀 İlk Kurulum

### 1. Repository'yi Klonlama

```bash
# HTTPS ile
git clone https://github.com/your-org/TezaverMac.git
cd TezaverMac

# SSH ile (önerilir)
git clone git@github.com:your-org/TezaverMac.git
cd TezaverMac
```

### 2. Python Environment Kurulumu

#### Önerilen Yöntem: pyenv

```bash
# pyenv kurulumu (macOS)
brew install pyenv

# Python 3.11 kurulumu
pyenv install 3.11.7
pyenv local 3.11.7

# Doğrulama
python --version  # Python 3.11.7 görmelisiniz
```

#### Alternatif: System Python

```bash
# Python versiyonunu kontrol edin
python3 --version

# 3.11 değilse, sisteminize uygun şekilde kurun
```

### 3. Virtual Environment Oluşturma

```bash
# Virtual environment oluştur
python -m venv venv

# Aktive et (macOS/Linux)
source venv/bin/activate

# Aktive et (Windows)
venv\Scripts\activate

# Doğrulama
which python  # venv içindeki python'u göstermeli
```

### 4. Bağımlılıkları Yükleme

```bash
# Production dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Development dependencies (opsiyonel)
pip install -r requirements-dev.txt

# Doğrulama
pip list | grep streamlit
```

### 5. Environment Variables Konfigürasyonu

```bash
# .env dosyası oluştur
cp .env.example .env

# .env dosyasını düzenle
nano .env  # veya favori editörünüz
```

**.env içeriği:**
```bash
# Binance API Credentials
BINANCE_API_KEY=your_actual_binance_api_key_here
BINANCE_SECRET_KEY=your_actual_binance_secret_key_here

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=INFO

# Timezone Configuration
TIMEZONE_OFFSET_HOURS=3
```

**⚠️ ÖNEMLİ**: `.env` dosyasını asla Git'e eklemeyin!

### 6. İlk Veri Toplama (Pipeline)

```bash
# Full pipeline çalıştırma (10-15 dakika)
make pipeline-full

# Alternatif
PYTHONPATH=src python src/tezaver/run_pipeline.py --mode full
```

**Beklenen Çıktı:**
```
=== TEZAVER MAC FULL PIPELINE STARTING ===
Step 1/13: M2 - History update
Step 2/13: M3 - Feature build
...
=== FULL PIPELINE COMPLETED SUCCESSFULLY ===
```

### 7. UI Başlatma

```bash
# Makefile ile
make ui

# Alternatif
PYTHONPATH=src streamlit run src/tezaver/ui/main_panel.py
```

Tarayıcınızda `http://localhost:8501` adresini açın.

---

## 🖥️ Production Deployment

### Linux Sunucuda (Systemd ile)

#### 1. Kullanıcı Oluşturma

```bash
# Özel kullanıcı oluştur
sudo useradd -m -s /bin/bash tezaver
sudo su - tezaver

# Projeyi klonla
cd /opt
sudo git clone <repo-url> TezaverMac
sudo chown -R tezaver:tezaver /opt/TezaverMac
```

#### 2. Systemd Service Dosyası

`/etc/systemd/system/tezaver-ui.service`:

```ini
[Unit]
Description=Tezaver Mac Streamlit UI
After=network.target

[Service]
Type=simple
User=tezaver
WorkingDirectory=/opt/TezaverMac
Environment="PYTHONPATH=/opt/TezaverMac/src"
Environment="PATH=/opt/TezaverMac/venv/bin:/usr/bin"
ExecStart=/opt/TezaverMac/venv/bin/streamlit run src/tezaver/ui/main_panel.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. Service Başlatma

```bash
# Service'i yükle
sudo systemctl daemon-reload

# Enable (otomatik başlatma)
sudo systemctl enable tezaver-ui

# Başlat
sudo systemctl start tezaver-ui

# Durum kontrolü
sudo systemctl status tezaver-ui

# Logları görüntüle
sudo journalctl -u tezaver-ui -f
```

---

## 🔄 Otomatik Pipeline (Cron Jobs)

### Cron Konfigürasyonu

```bash
# Cron düzenle
crontab -e
```

**Önerilen Cron Jobs:**

```cron
# Full pipeline - Her gün saat 02:00'de
0 2 * * * cd /opt/TezaverMac && /opt/TezaverMac/venv/bin/python src/tezaver/run_pipeline.py --mode full >> /var/log/tezaver/pipeline.log 2>&1

# Fast pipeline - Her saat başı
0 * * * * cd /opt/TezaverMac && /opt/TezaverMac/venv/bin/python src/tezaver/run_pipeline.py --mode fast >> /var/log/tezaver/fast-pipeline.log 2>&1

# Log rotation - Her Pazar saat 03:00
0 3 * * 0 find /var/log/tezaver/ -name "*.log" -mtime +7 -delete
```

### Alternatif: Systemd Timer

`/etc/systemd/system/tezaver-pipeline.service`:

```ini
[Unit]
Description=Tezaver Mac Full Pipeline

[Service]
Type=oneshot
User=tezaver
WorkingDirectory=/opt/TezaverMac
Environment="PYTHONPATH=/opt/TezaverMac/src"
ExecStart=/opt/TezaverMac/venv/bin/python src/tezaver/run_pipeline.py --mode full
```

`/etc/systemd/system/tezaver-pipeline.timer`:

```ini
[Unit]
Description=Run Tezaver Pipeline Daily

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Etkinleştirme:
```bash
sudo systemctl enable tezaver-pipeline.timer
sudo systemctl start tezaver-pipeline.timer
sudo systemctl list-timers
```

---

## 🔒 Güvenlik Best Practices

### 1. API Key Güvenliği

```bash
# .env dosyası izinleri
chmod 600 .env

# Owner'ı kontrol edin
ls -la .env
# -rw------- 1 tezaver tezaver 234 Dec  5 20:00 .env
```

### 2. Firewall Ayarları (UFW)

```bash
# UFW yükle ve aktive et
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH'yi aç
sudo ufw allow 22

# Streamlit port'u (sadece local)
sudo ufw allow from 127.0.0.1 to any port 8501

# Enable
sudo ufw enable
sudo ufw status
```

### 3. Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/tezaver
server {
    listen 80;
    server_name tezaver.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Aktive etme:
```bash
sudo ln -s /etc/nginx/sites-available/tezaver /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. SSL/TLS (Let's Encrypt)

```bash
# Certbot kurulumu
sudo apt install certbot python3-certbot-nginx

# SSL sertifikası al
sudo certbot --nginx -d tezaver.yourdomain.com

# Otomatik renewal test
sudo certbot renew --dry-run
```

---

## 📊 Monitoring ve Logging

### Loglama Yapılandırması

**Dizin oluşturma:**
```bash
sudo mkdir -p /var/log/tezaver
sudo chown tezaver:tezaver /var/log/tezaver
```

**Log rotation** (`/etc/logrotate.d/tezaver`):
```
/var/log/tezaver/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 tezaver tezaver
    sharedscripts
    postrotate
        systemctl reload tezaver-ui > /dev/null 2>&1 || true
    endscript
}
```

### Monitoring ile Prometheus (Opsiyonel)

```bash
# Prometheus exporter ekle
pip install prometheus-client

# Metrics endpoint: /metrics
```

---

## 🔧 Bakım ve Güncelleme

### Güncelleme Prosedürü

```bash
# 1. Backup al
make backup  # veya
PYTHONPATH=src python src/tezaver/backup/run_backup.py

# 2. Git pull
git pull origin main

# 3. Dependencies güncelle
pip install -r requirements.txt --upgrade

# 4. Testleri çalıştır
make test

# 5. Service'i yeniden başlat
sudo systemctl restart tezaver-ui

# 6. Durumu kontrol et
sudo systemctl status tezaver-ui
```

### Rollback Prosedürü

```bash
# Git checkout
git checkout <previous-version-tag>

# Dependencies'i eski haline getir
pip install -r requirements.txt

# Restart
sudo systemctl restart tezaver-ui
```

---

## 🧪 Doğrulama Checklist

### Kurulum Sonrası Kontroller

- [ ] Python versiyonu doğru (`python --version`)
- [ ] Virtual environment aktif (`which python`)
- [ ] Tüm dependencies kurulu (`pip list`)
- [ ] `.env` dosyası mevcut ve doğru
- [ ] Pipeline başarılı çalıştı
- [ ] Log dosyaları oluştu
- [ ] UI erişilebilir (`http://localhost:8501`)
- [ ] Testler başarılı (`make test`)
- [ ] Cron jobs çalışıyor (`crontab -l`)

### Sorun Giderme

**Problem**: Streamlit başlamıyor

```bash
# Port kontrolü
netstat -tuln | grep 8501

# Logları kontrol et
tail -f /var/log/tezaver/ui.log
```

**Problem**: Pipeline hata veriyor

```bash
# Manuel çalıştır ve trace gör
PYTHONPATH=src python -m pdb src/tezaver/run_pipeline.py --mode full
```

**Problem**: CCXT bağlantı hatası

```bash
# API key kontrolü
python -c "from tezaver.core.config import BINANCE_API_KEY; print(bool(BINANCE_API_KEY))"

# Network testi
curl -I https://api.binance.com
```

---

## 📞 Destek

Sorun yaşarsanız:
1. Logları kontrol edin: `/var/log/tezaver/`
2. GitHub Issues'da arayın
3. Yeni issue açın (log snippets ekleyin)

**Faydalı Komutlar:**
```bash
# Sistem durumu
make check

# Detaylı logs
sudo journalctl -u tezaver-ui -n 100 --no-pager

# Resource kullanımı
top -u tezaver
```

---

**Son Güncelleme**: Aralık 2025  
**Deployment Versiyonu**: 2.0
