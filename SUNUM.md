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

3. **Örnek ekstreyi masaüstüne kopyalayın.** `ornek_ekstreler\hesap_hareketleri.csv` dosyasını
   kolay ulaşabileceğiniz bir yere koyun; sunumda hızlı seçersiniz.

4. **Klasör izlemeyi göstereceksiniz:** izlenecek klasöre bir ekstre kopyalayıp bırakmak için
   ikinci bir dosya hazır bulundurun (örneğin `ornek_ekstreler\kart_ekstresi.xlsx`).

5. Uygulamayı açın; veri bulunan en son ay kendiliğinden seçilir.

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

### 4. Hesap ve Kart — ekstre yükleme (1,5 dk)
**Dosya Seç** → `ornek_ekstreler\hesap_hareketleri.csv` → sütunların otomatik eşleştiğini
gösterin → **İçe Aktar**.

Sonra **"Ekstreyi kendiliğinden yükle"** bölümünü gösterin: anahtarı açın, izlenen klasöre
hazırladığınız ikinci ekstreyi kopyalayın ve birkaç saniye içinde "Ekstre bulundu" bildiriminin
geldiğini gösterin.

Bakiye kartının altındaki açıklamayı da okutun: bakiyenin bir çıpa tarihinden ve sonraki
hareketlerden nasıl hesaplandığı yazıyor.
Söylenecek: *"Her bankanın sütun adı ve sayı biçimi farklı; başlık satırını ve sütunları kendi
buluyor. Kart borcu ödemesini ve virmanı gider saymıyor, yoksa harcama iki kez sayılırdı.
Kullanıcının tek yaptığı iş bankadan dosyayı indirmek; klasör izleme açıksa uygulamaya hiç
dokunmuyor. Bakiyeyi de elle güncellemesi gerekmiyor, çıpadan hesaplanıyor."*

### 5. Mutabakat — teknik vurgu (1,5 dk) ⭐
**En önemli bölüm burası.** **Çiftleri Tara** → eşleşmeler listelenir → **Tümünü Seç** →
**Seçilenleri Birleştir**.

Söylenecek: *"Gerçek zamanlı banka API'si olmadığı için aynı harcama birden çok yoldan
girebiliyor: SMS anında geliyor, fişi aynı gün okutuyorum, ekstre ay sonunda geliyor. Tutarı
aynı ve tarihi üç güne kadar yakın kayıtları eşleştirip olasılık puanı veriyor, bankanın resmi
kaydını asıl kabul edip diğerini siliyor. Bu olmadan Ekim gideri 18.498 ₺ görünüyordu, gerçek
değeri 15.604 ₺."*

### 6. Nakit Akışı (1 dk)
Takvimde her günün hareketi ve gün sonu bakiyesi. Gelecek günlerde sabit giderler düşecekleri
güne yerleşir.
Söylenecek: *"Diğer sayfalar geçmişi anlatıyor, bu sayfa önümüzdeki günleri. Bakiye ay içinde
eksiye düşüyorsa önceden uyarıyor."*

### 7. Öneriler — analiz motoru (1 dk)
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

**"SMS ve e-posta neden yok?"**
İkisi de yazıldı ve testleri geçiyor (`sms_parser.py` 14 farklı banka mesajında doğru sonuç
veriyor). Ancak SMS için telefon ile bilgisayarın aynı ağda olması, güvenlik duvarı izni ve
Play Store dışından uygulama kurulması; Gmail için uygulama şifresi üretilmesi gerekiyordu.
Kurulum maliyeti günlük kullanımı anlamsız kıldığı için arayüzden çıkarıldı, kodları projede
duruyor. Bunun yerine manuel işi azaltmaya odaklanıldı: klasör izleme ve türetilmiş bakiye.

**"Bunu insanlar kullanır mı?"**
Birden fazla bankası olan, nakit de harcayan ve verisini üçüncü tarafa vermek istemeyen biri için
anlamlı. Tek bankası olup yalnızca kartla harcayan biri kendi banka uygulamasını kullansın.
Yaygın benimsenme için masaüstü olması ve Python kurulumu gerektirmesi engel; Çözdüğü üç gerçek problem var (çok bankalı tablo, nakit harcama, verinin yerel
kalması) ama bunun kullanıcıya ulaşması için web veya mobil sürüm gerekir. Analiz motoru
(`insights.py`, `analyzer.py`, `reconcile.py`, `statement.py`) olduğu gibi taşınabilir.

**"En zor kısım neydi?"**
Veriyi göstermek değil, aynı harcamanın birden çok kaynaktan gelmesini çözmek ve geçmişten
düzenli ödeme örüntüsü çıkarmak. İlk denemede market harcamaları abonelik sanılıyordu; ayırt
edici özelliğin tutar değil takvim olduğu test sırasında ortaya çıktı.
