#!/bin/bash
# Tezaver - Tek Tuşla Kurulum Sihirbazı (Hetzner/Ubuntu)
# Kullanım: Bu dosyanın içeriğini sunucuya yapıştırın veya dosyayı çalıştırın.

# Renkler
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Tezaver Bulut Kurulum Sihirbazı ===${NC}"
echo "Sistem hazırlanıyor..."

# 1. Docker Kurulumu
if ! command -v docker &> /dev/null; then
    echo -e "${BLUE}[1/4] Docker yükleniyor...${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y docker.io docker-compose-v2 git
else
    echo -e "${GREEN}[1/4] Docker zaten yüklü.${NC}"
fi

# 2. Projeyi İndirme (GitHub)
echo -e "${BLUE}[2/4] Tezaver projesi indiriliyor...${NC}"
# Eğer klasör varsa güncelle, yoksa indir
if [ -d "tezaver" ]; then
    echo "Klasör mevcut, güncelleniyor..."
    cd tezaver
    git pull
else
    # Not: Private repo ise burada kullanıcı adı/şifre soracaktır
    git clone https://github.com/absaglam/tezaver.git
    cd tezaver
fi

# 3. Klasör Ayarları
echo -e "${BLUE}[3/4] Veri klasörleri hazırlanıyor...${NC}"
mkdir -p docker/cloud/data
mkdir -p docker/cloud/out

# 4. Başlatma
echo -e "${BLUE}[4/4] Robot başlatılıyor (Build)...${NC}"
cd docker/cloud
docker compose up -d --build

echo -e "${GREEN}=== KURULUM BAŞARIYLA TAMAMLANDI! ===${NC}"
echo ""
echo "Robot şu an arka planda çalışıyor."
echo "Logları izlemek için şu komutu yazın:"
echo "---------------------------------------------------"
echo "cd ~/tezaver/docker/cloud && docker compose logs -f"
echo "---------------------------------------------------"
