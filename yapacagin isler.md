# Yapılacak İşler Listesi (Open-Starship Projesi)

Bu belge, SpaceX Starship mimarisindeki temel fiziksel ve operasyonel darboğazları çözen üç bağımsız kütüphanenin ve ortak geçit hattının geliştirme adımlarını içerir.

---

## 1. Faz: starship-flip-gnc (Uçuş Dinamiği ve İniş Çevirme Optimizatörü)
- [x] 1.1 Araç fiziksel özelliklerini modelle (kuru kütle, iniş yakıt kütlesi, eylemsizlik momenti, Raptor 3 itki ve gimbal sınırları).
- [x] 1.2 Aerodinamik kuvvet modelini kodla (hücum açısına bağlı sürükleme ve kaldırma katsayıları, atmosferik yoğunluk profili).
- [x] 1.3 3-DoF iniş yörünge çözücüsünü yaz (yatay düşüşten 90 derece dikey inişe geçiş, doğrudan kolokasyon ve sınır şartları).
- [x] 1.4 Telemetri ihracatçısını yaz (zaman serisi ivme, açısal hız, itki vektörü ve aerotermal dinamik basınç çıktıları - JSON/CSV).
- [x] 1.5 Birim testleri yaz ve çalıştır (`test_models.py`, `test_aerodynamics.py`, `test_trajectory.py`).
- [x] 1.6 `starship-flip-gnc/README.md` belgesini hazırla.

---

## 2. Faz: starship-cryo-slosh (Kriyojenik Yakıt Çalkantısı ve Gaz Girişi Simülatörü)
- [x] 2.1 Burun ve metan header tank geometrilerini ve sıvı özelliklerini (LOX, LCH4) modelle.
- [x] 2.2 Eşdeğer mekanik sarkaç çalkantı denklemlerini kodla (doğal frekans, sönümleme oranı, sıvı serbest yüzey yer değiştirmesi).
- [x] 2.3 `starship-flip-gnc` telemetrisini girdi alan ve Runge-Kutta 4 (RK4) ile çalkantıyı çözen simülatörü kur.
- [x] 2.4 Emiş borusu gaz alma (ullage gas ingestion) eşik tespitini ve kontrolcüye yansıyacak bozulma torkunu hesapla.
- [x] 2.5 Birim testleri yaz ve çalıştır (`test_tank.py`, `test_slosh.py`, `test_telemetry_coupling.py`).
- [x] 2.6 `starship-cryo-slosh/README.md` belgesini hazırla.

---

## 3. Faz: starship-tps-vision (Isı Kalkanı Hasar Tespit ve Muayene Hattı)
- [x] 3.1 Uçuş telemetrisinden gelen ısı akısı ve dinamik basınca göre gövde karo koordinat risk haritası üreticisini yaz.
- [x] 3.2 Sentetik altıgen karo muayene görüntüsü/ızgarası üreticisini kodla (kırık, eksik, yerinden oynamış karo anomalileri).
- [x] 3.3 Anomali tespit algoritmasını yaz (karo aralık sapmaları, yüzey kayıpları ve uçuş risk katsayısı ağırlıklandırması).
- [x] 3.4 Bakım ekipleri için JSON ve Markdown muayene raporlayıcısını kodla.
- [x] 3.5 Birim testleri yaz ve çalıştır (`test_thermal_map.py`, `test_synthetic.py`, `test_detector.py`, `test_reporter.py`).
- [x] 3.6 `starship-tps-vision/README.md` belgesini hazırla.

---

## 4. Faz: Uçtan Uca Entegrasyon ve Dağıtım Dokümantasyonu
- [x] 4.1 Üç modülü birbirine bağlayan `run_pipeline.py` orkestrasyon betiğini yaz.
- [x] 4.2 Kök dizindeki ana `README.md` dosyasını oluştur (mimari, kurulum, hızlı başlangıç, GitHub Sponsor linki ve 3 yıllık geliştirme notu).
- [x] 4.3 Tüm test paketini uçtan uca çalıştır ve doğrula (22/22 birim testi başarılı).
- [x] 4.4 `yaptigin isler.md` ve `devam notu.md` belgelerini güncelle.
