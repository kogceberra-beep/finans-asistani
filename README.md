# Akıllı Finans Asistanı

Harcamaları **manuel giriş**, **OCR ile fiş okuma** ve **banka API entegrasyonu** (mock servis) ile toplayan;
aylık bütçeyi izleyip kişiselleştirilmiş tasarruf önerileri üreten masaüstü uygulaması.

## Özellikler
- SQLite ile harcama, kategori, birikim hedefi ve ayar saklama
- **Gerçek banka verisi:** hesap hareketleri ve kart ekstresi (CSV/Excel) içe aktarma; sütunlar otomatik eşleşir, tekrar yüklemede kayıt çoğalmaz, kart borcu ödemesi/virman gider sayılmaz, iadeler düşülür
- **Ekstreyi kendiliğinden yükleme:** seçilen klasörü izler, bankadan indirdiğiniz hesap ekstresini tanıyıp içeri aktarır; dosya seçmek gerekmez
- **Türetilmiş bakiye:** bakiye bir "çıpa" tarihinden ve sonraki hareketlerden hesaplanır, elle güncellemek gerekmez
- **Mutabakat:** aynı harcama fiş ve ekstreden ayrı ayrı girdiğinde çift sayımı bulur ve bankanın resmi kaydını asıl kabul ederek birleştirir
- **Nakit akışı takvimi:** ayın gün gün para giriş/çıkışı, sabit giderlerin hangi gün düşeceği ve bakiyenin nasıl seyredeceği; bakiye eksiye düşecekse önceden uyarır
- **Öğrenen kategoriler:** bir kaydın kategorisini düzelttiğinizde aynı işyerinin sonraki harcamaları otomatik o kategoriye düşer
- Gelir takibi ve hesap bakiyesi
- Ay seçici ile geçmiş aylar
- FastAPI mock banka servisi (Açık Bankacılık/ÖHVPS yerine demo; gerçek erişim lisans ve müşteri rızası gerektirir)
- CustomTkinter arayüzü: karanlık/aydınlık mod, halka grafik, kategori bütçe çubukları
> **Not:** SMS ve e-posta entegrasyonları arayüzden kaldırılmıştır. Kodları projede durur
> (`sms_parser.py`, `sms_server.py`, `gmail_client.py`) ve testleri geçer, ancak ikisi de
> kullanıcıdan ek kurulum istediği (aynı Wi-Fi ağı, güvenlik duvarı izni, Play Store dışı
> uygulama, Gmail uygulama şifresi) için günlük kullanımda pratik bulunmamıştır. Ayrıntı için
> aşağıdaki "Sınırlar" bölümüne bakın.

- **SMS çözümleme (arayüzde değil):** telefondan iletilen banka harcama SMS'lerini çözümler (tutar, işyeri, kart son 4 hane, gelir/gider/iade); limit, asgari ödeme ve kampanya mesajlarını eler
- **Gmail çözümleme (arayüzde değil):** IMAP + uygulama şifresi ile fiş/fatura/sipariş e-postalarını tarar, gövdeden ve PDF ekinden tutar çıkarır (posta kutusu yalnızca okunur)
- Tesseract OCR ile fişten tutar, tarih ve işyeri okuma (`ornek_fisler/` klasöründe test fişleri var)
- Analiz motoru: bütçe aşımı uyarıları, günlük limit, aylık trend

> Derste göstereceklerin sırası ve ne söyleneceği için **[SUNUM.md](SUNUM.md)** dosyasına bakın.

## Neden bu uygulama

Ayda bir kez bankadan dosya indirirsiniz; gerisini uygulama yapar ve ay bitmeden ne olacağını söyler.

- **Birden fazla bankayı tek tabloda görmek.** Banka uygulamaları yalnızca kendi bankasını görür;
  iki hesabın ve nakdin toplamını gösteren başka bir yer yoktur.
- **Geçmişi değil geleceği anlatması.** Banka uygulaması "geçen ay ne harcadın" der. Bu uygulama
  "ayın 2'sinde kira, 17'sinde elektrik çıkacak, 15'inde bakiyen şuraya iniyor" der.
- **Nakit ve fişin görünmesi.** Banka nakit harcamayı yapısal olarak göremez; fiş okuma bu boşluğu doldurur.
- **Verinin yerel kalması.** Finansal geçmiş üçüncü bir tarafa gitmez, abonelik ücreti yoktur.

**Kimin kullanmaması gerektiği:** tek bankası olan, yalnızca kartla harcayan ve telefonunda görmek
isteyen biri kendi banka uygulamasıyla aynı bilgiye ulaşır.

**Aylık emek:** iki bankadan ekstre indirmek (~2 dakika) ve nakit harcama varsa elle eklemek.

## Kurulum
```bash
pip install -r requirements.txt
```
OCR için ayrıca **Tesseract** gerekir ([Windows yükleyici](https://github.com/UB-Mannheim/tesseract/wiki),
Linux: `sudo apt install tesseract-ocr tesseract-ocr-tur`, macOS: `brew install tesseract tesseract-lang`).
Türkçe dil paketi yoksa İngilizceye düşer; tutar ve tarih yine okunur.

## Örnek veriyle hızlı başlangıç
Uygulamayı dolu bir veritabanıyla denemek için:
```bash
python ornek_veri.py
```
Son dört ay için gerçekçi bir geçmiş üretir: maaş, kira, internet, telefon, elektrik, Netflix ve Spotify
gibi düzenli ödemeler; Şok, BİM, Migros, A101 alışverişleri, restoran ve ulaşım harcamaları. Analiz
özelliklerinin görünmesi için ayrıca şunları bilerek kurar: Netflix'e gelen zam, iptal edilmiş bir
Spotify aboneliği, olağan dışı büyüklükte bir alışveriş ve Mutabakat sayfasında bulunacak iki çift kayıt.
Bütçe limitleri ve hesap bakiyesi de üretilen veriye göre ayarlanır.

## Çalıştırma (iki ayrı terminal)
```bash
# 1) Banka servisi
python -m uvicorn mock_bank:app --port 8001

# 2) Uygulama
python app.py
```
Windows'ta ikisini birden `baslat.bat` ile de açabilirsiniz. Banka sekmesinden **Şimdi Senkronize Et**'e basın.
Servis dokümantasyonu: http://127.0.0.1:8001/docs

## Dosyalar
| Dosya | Görev |
|---|---|
| `database.py` | SQLite şeması ve CRUD |
| `mock_bank.py` | FastAPI mock banka servisi |
| `textparse.py` | SMS ve e-posta metinlerinden tutar/tarih/işyeri çıkaran ortak katman |
| `sms_parser.py` | Banka SMS'lerinin çözümlenmesi |
| `sms_server.py` | Telefondan gelen SMS'leri karşılayan yerel servis (port 8002) |
| `gmail_client.py` | Gmail IMAP istemcisi ve e-posta çözümleme |
| `ornek_veri.py` | Deneme/sunum için gerçekçi örnek veri üreteci |
| `insights.py` | Tekrarlayan ödeme tespiti, olağan dışı harcama analizi, ay sonu tahmini |
| `reconcile.py` | Kaynaklar arası çift kayıt eşleştirme ve birleştirme |
| `statement.py` | Ekstre (CSV/XLSX) okuma, sütun eşleştirme, ayrıştırma, içe aktarma |
| `bank_client.py` | Servisten işlem çeker, kategorileyip kaydeder (mükerrer kaydı engeller) |
| `ocr.py` | Fiş görüntüsünden tutar/tarih/işyeri çıkarma |
| `analyzer.py` | Kategori tahmini, bütçe durumu, trend, uyarı ve öneri motoru |
| `app.py` | Arayüz |

## SMS entegrasyonu
1. Uygulamada **SMS** sekmesinden *SMS alıcısını başlat* anahtarını açın; ekranda `http://<ip>:8002/sms` adresi çıkar.
2. Telefona bir *SMS Forwarder* uygulaması kurun (Android'de ücretsiz seçenekler vardır) ve gelen SMS'leri
   bu adrese **POST** edecek şekilde ayarlayın (gövde alanı: `text`). Telefon ile bilgisayar aynı Wi-Fi ağında olmalıdır.
3. Gelen bildirim listeye düşer; **siz onaylamadan harcama olarak kaydedilmez**.

Telefon uygulaması kurmadan denemek için SMS metnini aynı sayfadaki kutuya yapıştırıp *Metni Çözümle* diyebilirsiniz.

## Gmail entegrasyonu
Normal Gmail şifresi çalışmaz. Google Hesabı → Güvenlik → **2 Adımlı Doğrulama**'yı açın, aynı sayfadaki
**Uygulama şifreleri** bölümünden 16 haneli bir şifre üretin ve **E-posta** sekmesine girin. Uygulama posta
kutusunu yalnızca okur. Şifre, `.gitignore` içindeki `finance.db` dosyasında saklanır; paylaşılan bir
bilgisayarda kullanmayın ve uygulama şifresini Google hesabınızdan istediğiniz an iptal edebilirsiniz.

> Not: Gerçek kart hareketlerini bir API'den doğrudan çekmek (ÖHVPS / Açık Bankacılık) lisanslı kuruluş ve
> müşteri rızası akışı gerektirir; bireysel kullanıcıya API anahtarı verilmez. Bu yüzden gerçek veri
> ekstre, SMS ve e-posta yollarıyla alınır.

## Mutabakat neden gerekli
Gerçek zamanlı bir banka API'si olmadığı için veri üç ayrı hızda gelir:

| Kaynak | Ne zaman gelir | Güvenilirlik |
|---|---|---|
| SMS | harcama anında | tutar doğru, işyeri adı kısaltılmış olabilir |
| Fiş (OCR) | aynı gün, siz okuttuğunuzda | kalem detayı var, okuma hatası olabilir |
| Ekstre | ay sonunda | bankanın resmi kaydı, en güvenilir |

Aynı alışveriş üçünden de girebileceği için harcama iki-üç kez sayılabilir. **Mutabakat** sayfası tutarı
aynı ve tarihi 3 güne kadar yakın olan kayıtları eşleştirir, işyeri adı benzerliğine göre bir olasılık
puanı verir ve onayınızla düşük öncelikli kaydı siler. Öncelik sırası: ekstre > SMS > fiş > elle giriş.
Ekstre içe aktarıldıktan sonra bu denetim otomatik çalışır.

## Analiz motoru

### Tekrarlayan ödemeler (abonelik / sabit gider)
Harcamalar marka adına göre gruplanır. Bir marka en az iki ayda görünüyor, ayda bir kez düşüyor ve
tutarı %35'ten az değişiyorsa **sabit gider** sayılır. Böylece kira ve Netflix abonelik olarak
tanınırken, her ay gidilen ama tutarı değişen market "değişken" kalır. Motor ayrıca aboneliğe gelen
zammı (199 ₺ → 249 ₺) ve artık düşmeyen, yani iptal edilmiş abonelikleri de bildirir.

### Olağan dışı harcama tespiti
Bir harcama, **önce aynı işyerindeki kendi geçmişiyle** kıyaslanır: her zaman 1.000 ₺ civarı
alışveriş yaptığınız markette 1.200 ₺ harcamanız olağan dışı değildir. İşyeri geçmişi yoksa kategori
medyanı kullanılır. Kira ve abonelikler tutarı yüksek ama düzenli olduğundan elenir.

### Ay sonu tahmini
Düz orantı (`harcanan / geçen gün × ayın günü`) yanıltıcıdır: ayın 2'sinde ödenen kira, günlük
harcama hızını olduğundan çok yüksek gösterir. Bu yüzden tahmin üç parçadan kurulur:

```
tahmin = şu ana kadar harcanan
       + (değişken harcama / geçen gün) × kalan gün
       + ay içinde düşmesi beklenen, henüz çekilmemiş sabit giderler
```

Örnek: ayın 5'inde 9.500 ₺ kira ve 1.230 ₺ market harcanmışken düz orantı **66.528 ₺** tahmin ederken,
bu yöntem **17.327 ₺** verir.

Aylık karşılaştırmalar da aynı mantıkla düzeltilmiştir: ay bitmemişse geçen ay da aynı güne kadar
kesilerek kıyaslanır, böylece ayın 5'inde "harcamanızı %90 azalttınız" gibi yanlış bir sonuç çıkmaz.

## Nakit akışı takvimi

Uygulamanın geri kalanı **geçmişi** anlatır (ne harcadın, nerede bütçeyi aştın). Bu sayfa **önümüzdeki
günleri** gösterir ve asıl günlük fayda buradadır.

Takvimde her gün için üstte o günün hareketi, altta gün sonu bakiyesi yazar. Geçmiş günlerde gerçekleşen
tutarlar, gelecek günlerde beklenen tutarlar görünür. Beklenen hareketler üç kaynaktan gelir:

- **Sabit giderler**, düştükleri güne yerleştirilir (kira ayın 2'sinde, Netflix 9'unda).
- **Düzenli gelirler** (maaş), aynı şekilde geldiği güne yerleştirilir.
- **Değişken harcama**, günlük ortalama olarak her güne dağıtılır.

Günlük ortalama hesaplanırken ayın ilk günlerinde yalnızca birkaç güne bakmak yanıltıcıdır; tek bir büyük
alışveriş ortalamayı ikiye katlar. Bu yüzden ortalama, ayın 10'una kadar geçen ayın ortalamasıyla
harmanlanır. Test senaryosunda bu düzeltme ay sonu tahminini **-8.733 ₺** gibi paniğe sürükleyen bir
rakamdan gerçekçi olan **+281 ₺**'ye çekmiştir.

Bakiye ay içinde herhangi bir gün eksiye düşüyorsa sayfanın üstünde kırmızı uyarı çıkar ve Öneriler
sayfasına da bir uyarı düşer: *"bu gidişle 30 Kasım'da bakiyeniz -5.719 ₺ seviyesine düşüyor."*

## Düzenli ödeme nasıl ayırt edilir

İlk denemelerde market ve kafe harcamaları "abonelik" sanılıyordu: dört ayda da görünüyorlardı ve aylık
medyan tutarları birbirine yakındı. Ayırt edici özelliğin tutar değil **takvim** olduğu buradan anlaşıldı.

Bir ödeme ancak şu üç şartı birden sağlarsa düzenli sayılır: en az iki ayda görünür, **her ayda tam olarak
bir kez** düşer ve düştüğü **gün aylar arasında en fazla 4 gün oynar**. Markete ayda birkaç kez, rastgele
günlerde gidildiği için bu eleme işe yarar.

Düzenli ödemeler ikiye ayrılır: tutarı da sabit olanlar (kira, Netflix) ve tutarı değişen düzenli faturalar
(elektrik). İkisi de nakit akışı takviminde beklenen ödeme olarak görünür, ama "zam geldi" uyarısı yalnızca
tutarı normalde sabit olanlar için üretilir — yoksa elektrik faturasının doğal dalgalanması her ay zam
sanılırdı.

## Sınırlar

Bu bölüm, projenin bilerek çözmediği veya çözemediği şeyleri listeler.

- **Gerçek zamanlı banka erişimi yok.** Türkiye'de resmi yol BKM ve TCMB'nin Açık Bankacılık
  altyapısıdır (ÖHVPS); üretim ortamına erişim lisanslı kuruluş olmayı ve müşteri rızası akışını
  gerektirir, bireysel geliştiriciye API anahtarı verilmez. Veri bu yüzden ekstre, fiş ve elle
  giriş yoluyla alınır. Hesap bakiyesi de elle girilir.
- **Masaüstü uygulamasıdır.** Para telefonda harcanır, uygulama bilgisayardadır. Harcamanın
  anında kaydedilmesi bu yapıda mümkün değildir.
- **SMS ve e-posta denendi, arayüzden çıkarıldı.** SMS için telefon ile bilgisayarın aynı ağda
  olması, güvenlik duvarı izni ve Play Store dışından bir uygulama kurulması gerekiyordu;
  Gmail için uygulama şifresi üretilmesi gerekiyordu. Çözümleyiciler çalışıyor ve testleri
  geçiyor, ancak kurulum maliyeti günlük kullanımı anlamsız kılıyordu. Mobil bir sürümde bu
  maliyetlerin çoğu ortadan kalkar.
- **Kurulum zahmetlidir.** Python, bağımlılıklar ve fiş okuma için Tesseract kurulumu gerekir.
- **Tek kullanıcı, tek cihaz.** Senkronizasyon ve hesap yönetimi yoktur; veri yalnızca
  `finance.db` dosyasında, kullanıcının bilgisayarında durur.
