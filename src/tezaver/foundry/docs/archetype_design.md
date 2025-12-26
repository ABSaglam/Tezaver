# 🧪 Dökümhane Simyacısı (The Alchemist) Tasarımı

Simyacı, Dökümhane'nin **Pattern Discovery (Desen Keşfi)** motorudur.
Amacı: Tekil rallilerin gürültüsünden arınıp, onların ortak "Özünü" (Arketipi) damıtmaktır.

## 🧱 1. Nasıl Çalışır? (Metodoloji)

Simyacı, 3 aşamalı bir damıtma süreci uygular:

### Aşama A: Normalizasyon (Tencereye Atma)
Farklı zamanlarda olmuş 50 tane "DIAMOND" rallisini alır.
Hepsini "Olay Anı" (t=0) merkezli olacak şekilde üst üste bindirir.
*   **Zaman Eşitleme:** Hepsinin t=0 noktası (bizim onayladığımız giriş barı) çakıştırılır.
*   **Fiyat Eşitleme:** Hepsinin t=0 anındaki fiyatı 100 kabul edilir (Percentage Normalization).
*   **Sonuç:** Spagetti gibi görünen ama aynı noktadan düğümlenmiş çizgiler yumağı.

### Aşama B: Kümeleme (Ayrıştırma)
Bu yumak içindeki benzer karakterleri gruplar.
*   "Hızla fırlayanlar" (Tip A)
*   "Önce bir dip yapıp (Spring) sonra kalkanlar" (Tip B)
*   "Yavaş yavaş tırmananlar" (Tip C)
Bunu yapmak için **DTW (Dynamic Time Warping)** veya **K-Means** algoritmalarını kullanır.

### Aşama C: Özüt Çıkarma (Arketip Yaratma)
Her bir grubun "Ortalamasını" (Centroid) alır. Bu artık sanal bir çizgidir, gerçeğin idealize edilmiş halidir.
Buna **ARKETİP** denir.

---

## 📄 2. Çıktı Kartı: Arketip Kimliği

Simyacı işini bitirdiğinde bize şöyle bir kart verir:

**🏷️ Arketip: BTC_15m_DIAMOND_TYPE_A**
*   **Üye Sayısı:** 42 adet ralli (Güçlü Kanıt)
*   **Karakter:** "Ani Patlama" (Explosive Breakout)
*   **Ortalama Kazanç:** %4.2
*   **Ortalama Süre:** 12 Bar
*   **Ortak Göstergeler (The Soul):**
    *   Ralliden 2 bar önce RSI mutlaka 40'ın altına inmiş.
    *   Olay anında Hacim ortalamanın 3 katına çıkmış.

---

## 🏗️ 3. Teknik Mimari

1.  **`ClusteringService`**: Matematiksel işleri yapar (Pandas/Scikit-learn).
2.  **`ArchetypeStoryteller`**: İstatistiklerden "Hikaye" çıkarır (RSI 40 altıydı vb.).
3.  **UI Entegrasyonu:** Dökümhaneye "🧪 Simyacı" sekmesi eklenir. Kullanıcı "Diamondları Analiz Et" der ve çıkan Arketipleri görür.

## 🚀 Faydası
Matrix, 1000 tane farklı ralli yerine bu 3-5 tane "Ana Karakteri" öğrenir. Böylece hem daha hızlı çalışır hem de "ezberlemek" yerine "anlamış" olur.
