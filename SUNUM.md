# Sunum Rehberi

Derste uygulamayı gösterirken izlenecek sıra. Toplam 6-8 dakika.

## Dersten ÖNCE yapılacaklar

1. **Veriyi yükleyin.** Analiz özelliklerinin çalışması için en az iki aylık veri gerekir;
   elle girmeyin, hazır üreteci kullanın:
   ```powershell
   cd C:\finans_asistani
   python ornek_veri.py
   ```
   Komut başta `Veritabanı: C:\finans_asistani\finance.db` yazdırmalı. Aynı yolu `app.py` de
   yazdırır; ikisi farklıysa veri görünmez.

2. **Tesseract kurulu mu kontrol edin** (fiş okuma için):
   ```powershell
   & "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
   ```

3. **Gmail taramasını evde yapın.** Derste internet olmayabilir. Evde **E-posta** sekmesinden
   tarayın ama **kaydetmeyin**. Bulunan e-postalar listede bekler; derste sadece "Seçilenleri
   Kaydet" demeniz yeter. Böylece internet olmadan da gösterebilirsiniz.

4. **SMS için ağ kurulumuna güvenmeyin.** Derste telefon-bilgisayar aynı ağda olmayabilir,
   güvenlik duvarı engelleyebilir. Aşağıdaki **yapıştırma** yöntemi aynı kodu çalıştırır ve
   her koşulda çalışır.

5. Uygulamayı açıp sağ üstten **içinde bulunulan ayı** seçin.

---

## Sunum sırası

### 1. Panel — "Bu ay ne oldu?" (1 dk)
Halka grafikte kategori dağılımı, sağda bütçe çubukları, altta uyarılar.
Söylenecek: *"Banka uygulaması size işlem listesi verir; burada kategori dağılımı ve bütçe
durumu var."*

### 2. Harcamalar — elle giriş (30 sn)
Tutar, tarih, açıklama girip **Harcama Ekle**. Kategori "Otomatik" bırakılırsa açıklamadan
tahmin edilir (örn. "Migros" yazın → Market).

Sonra bir kaydı seçip kategorisini değiştirin, **"Bu işyerini hep böyle kategorile"** açık olsun.
Söylenecek: *"Düzeltme yaptıkça öğreniyor; aynı işyerinin sonraki harcamaları otomatik o
kategoriye düşüyor."*

### 3. Fiş Oku — OCR (1 dk)
**Fiş Görseli Seç** → `ornek_fisler\fis1_market.png`
Beklenen sonuç: tutar **757,35**, tarih **2026-10-24**, işyeri **ÖRNEK MARKET A.Ş.**
Ham metin alt kutuda görünür. **Onayla ve Kaydet**.

### 4. SMS (1 dk)
**SMS** sekmesi → alttaki kutuya aşağıdaki metni yapıştırın → **Metni Çözümle**:

```
Sayin musterimiz, 1234 nolu kredi kartiniz ile MIGROS ANKARA'da 245,50 TL tutarinda islem gerceklestirilmistir.
```

Listeye düşer: MİGROS ANKARA, 245,50 ₺, Gider. Satıra tıklayıp **Seçilenleri Kaydet**.

İkinci örnek (gelir olarak tanınır):
```
Hesabiniza 32.500,00 TL maas odemesi yatmistir. Bakiye: 45.120,30 TL
```

Üçüncü örnek (bilgilendirme mesajı, harcama sayılmaz):
```
Kart borcunuz icin asgari odeme tutari 1.250,00 TL'dir. Son odeme tarihi 05.11.2026
```

Söylenecek: *"Çözümleyici tutarı, işyerini, tarihi ve kart son dört hanesini ayırıyor; gelir ile
gideri ayırt ediyor; limit ve asgari ödeme gibi bilgilendirme mesajlarını harcama saymıyor.
Telefondan canlı almak için de bir webhook servisi var ama aynı ağ gerektirdiği için derste
yapıştırma yöntemini kullanıyorum."*

### 5. E-posta (30 sn)
**E-posta** sekmesi. Evde taradıysanız liste zaten dolu. Bir satır seçip **Seçilenleri Kaydet**.
Söylenecek: *"Gmail'e IMAP ve uygulama şifresiyle bağlanıyor, posta kutusunu yalnızca okuyor.
Fatura ve sipariş e-postalarını süzüp gövdeden veya PDF ekinden tutarı çıkarıyor."*

### 6. Hesap ve Kart — ekstre yükleme (1 dk)
**Dosya Seç** → `ornek_ekstreler\hesap_hareketleri.csv` → sütunların otomatik eşleştiğini
gösterin → **İçe Aktar**.
Söylenecek: *"Her bankanın sütun adı ve sayı biçimi farklı; başlık satırını ve sütunları kendi
buluyor. Kart borcu ödemesini ve virmanı gider saymıyor, yoksa harcama iki kez sayılırdı."*

### 7. Mutabakat — teknik vurgu (1,5 dk) ⭐
**En önemli bölüm burası.** **Çiftleri Tara** → eşleşmeler listelenir → **Tümünü Seç** →
**Seçilenleri Birleştir**.

Söylenecek: *"Gerçek zamanlı banka API'si olmadığı için aynı harcama birden çok yoldan
girebiliyor: SMS anında geliyor, fişi aynı gün okutuyorum, ekstre ay sonunda geliyor. Tutarı
aynı ve tarihi üç güne kadar yakın kayıtları eşleştirip olasılık puanı veriyor, bankanın resmi
kaydını asıl kabul edip diğerini siliyor. Bu olmadan Ekim gideri 18.498 ₺ görünüyordu, gerçek
değeri 15.604 ₺."*

### 8. Nakit Akışı (1 dk)
Takvimde her günün hareketi ve gün sonu bakiyesi. Gelecek günlerde sabit giderler düşecekleri
güne yerleşir.
Söylenecek: *"Diğer sayfalar geçmişi anlatıyor, bu sayfa önümüzdeki günleri. Bakiye ay içinde
eksiye düşüyorsa önceden uyarıyor."*

### 9. Öneriler — analiz motoru (1 dk)
Üstte aylık sabit giderler, altta uyarılar: Netflix'e gelen zam, iptal edilmiş Spotify, olağan
dışı harcama.
Söylenecek: *"Düzenli ödemeyi tutarından değil takviminden tanıyor: her ay tam bir kez ve hep
aynı güne yakın düşüyorsa düzenli sayılıyor. Markete ayda birkaç kez rastgele günlerde
gidildiği için eleniyor."*

---

## Soru gelirse

**"Gerçek banka entegrasyonu neden yok?"**
Türkiye'de resmi yol BKM ve TCMB'nin Açık Bankacılık altyapısı (ÖHVPS). Üretim ortamına erişim
lisanslı kuruluş olmayı ve müşteri rızası akışını gerektiriyor; bireysel geliştiriciye API
anahtarı verilmiyor. Bu yüzden veri ekstre, fiş, SMS ve e-posta üzerinden alınıyor.

**"Bunu insanlar kullanır mı?"**
Bugünkü haliyle hayır: masaüstü uygulaması, Python ve Tesseract kurulumu gerekiyor, ekstre elle
yükleniyor. Çözdüğü üç gerçek problem var (çok bankalı tablo, nakit harcama, verinin yerel
kalması) ama bunun kullanıcıya ulaşması için web veya mobil sürüm gerekir. Analiz motoru
(`insights.py`, `analyzer.py`, `reconcile.py`, `statement.py`) olduğu gibi taşınabilir.

**"En zor kısım neydi?"**
Veriyi göstermek değil, aynı harcamanın birden çok kaynaktan gelmesini çözmek ve geçmişten
düzenli ödeme örüntüsü çıkarmak. İlk denemede market harcamaları abonelik sanılıyordu; ayırt
edici özelliğin tutar değil takvim olduğu test sırasında ortaya çıktı.
