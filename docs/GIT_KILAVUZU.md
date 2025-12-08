# 🚀 Tezaver Git Gönderim Kılavuzu

Otomatik gönderim sırasında karşılaşılan "Büyük Dosya" ve "Yetkilendirme" sorunlarını aşmak için aşağıdaki adımları sırasıyla terminalinizde uygulayın.

## Adım 1: Terminali Açın ve Klasöre Gidin

Halihazırda projenin olduğu klasörde olduğunuzu varsayıyoruz. Emin olmak için:
```bash
cd /Users/alisaglam/TezaverMac
```

## Adım 2: Büyük Dosyaları Temizleme (Reset)

Daha önce yanlışlıkla `backups` klasöründeki büyük zip dosyaları commitlenmiş olabilir. Bunları temizlemek için son commit'i geri alalım (dosyalarınız silinmez, sadece paket açılır):

```bash
git reset HEAD~1
```
*(Eğer "ambiguous argument" hatası alırsanız `git reset` yazıp enter'a basmanız yeterlidir).*

## Adım 3: Temiz Kurulum ile Dosyaları Ekleme

Ben `.gitignore` dosyasını güncelledim, artık zip dosyalarını görmezden gelecek. Şunları çalıştırın:

```bash
git add .
git commit -m "Tezaver Manual Push: Clean Code"
```

## Adım 4: Github'a Gönderme (Push)

Şimdi dosyaları gönderelim. Bu komutu yazdığınızda sizden Kullanıcı Adı ve Şifre isteyebilir:

```bash
git push -u origin main
```

---

### 🔑 Şifre Yerine "Personal Access Token" Kullanımı!

GitHub artık terminalden normal hesap şifresi ile girişi kabul etmiyor. Şifre sorduğunda **"Personal Access Token (PAT)"** girmeniz gerekir.

**Eğer Token'ınız yoksa:**
1. GitHub.com'a gidin -> **Settings (Ayarlar)**
2. En altta **Developer settings** -> **Personal access tokens** -> **Tokens (classic)**
3. **Generate new token (classic)** butonuna basın.
4. "Repo" kutucuğunu işaretleyin (tüm repo izinleri için).
5. Token'ı oluşturun ve kopyalayın (`ghp_...` ile başlar).
6. Terminalde şifre sorulduğunda bu kodu yapıştırın.

*(Not: Terminalde şifreyi yapıştırırken ekranda karakter görünmez, yapıştırıp Enter'a basın.)*

---

### Alternatif: Force Push (Sorun Çıkarsa)

Eğer yukarıdakiler hata verirse ve "history mismatch" derse, zorla göndermek için (dikkatli olun, uzaktaki geçmişi ezer):
```bash
git push -f origin main
```
