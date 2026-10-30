# Open-Starship

Starship roket mimarisinin karşılaştığı üç temel fiziksel ve operasyonel darboğazı çözen, birbirine bağlı açık kaynak mühendislik araçları paketi:

1. **`starship-flip-gnc`**: Yatay gövde düşüşünden (belly-flop) dikey inişe geçiş (landing flip) yörünge optimizasyonu ve itki vektör kontrolü (TVC).
2. **`starship-cryo-slosh`**: İniş manevrası sırasında burun ve metan header tanklarındaki kriyojenik yakıt çalkantısı, kütle merkezi kayması ve emiş hattı gaz yutma (ullage gas ingestion) analizi.
3. **`starship-tps-vision`**: Uçuş aerotermal yük verilerini girdi alarak gövde seramik karolarındaki kırılma, düşme ve boşluk genleşmelerini tespit edip bakım iş emirleri üreten muayene hattı.

---

## Sistem Mimarisi ve Veri Akışı

```
[ starship-flip-gnc ]
       │
       │ (Uçuş Telemetrisi: t, a_lat, a_ax, omega, dynamic_pressure, heat_flux)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[ starship-cryo-slosh ]               [ starship-tps-vision ]
  - Tank içi sarkaç çalkantısı          - Gövde bölgesel aerotermal risk haritası
  - Sıvı batma derinliği (submergence)  - Hasar tespiti (eksik, çatlak, kırık)
  - Turbopompa gaz alma uyarısı         - Öncelik sıralı bakım iş emri (Markdown)
  - Bozulma torku telemetrisi
```

---

## Dizin Yapısı

```
open-starship/
├── starship-flip-gnc/     # Uçuş dinamiği ve 3-DoF yörünge çözücü
├── starship-cryo-slosh/   # Kriyojenik sıvı çalkantısı ve gaz giriş analizörü
├── starship-tps-vision/   # Isı kalkanı (TPS) hasar tespit ve iş emri hattı
├── run_pipeline.py        # 3 modülü birbirine bağlayan uçtan uca orkestratör
├── yapacagin isler.md     # Planlanan iş listesi
├── yaptigin isler.md      # Tamamlanan işler ve doğrulama raporu
├── devam notu.md          # Sonraki geliştiriciler için mimari notlar
└── README.md              # Ana proje kılavuzu
```

---

## Hızlı Başlangıç

Harici bağımlılık gerekmez. Sistem standart Python 3.9+ kütüphaneleriyle çalışır.

### Tüm Boru Hattını Tek Komutla Çalıştırma

```bash
python3 run_pipeline.py pipeline_artifacts
```

Bu komut sırasıyla:
1. İniş çevirme yörüngesini çözer, yumuşak temas telemetrisini `pipeline_artifacts/flight_telemetry.json` dosyasına yazar.
2. Bu telemetriyi okuyup header tank çalkantısını simüle eder, gaz yutma riskini `pipeline_artifacts/slosh_dynamics.json` içine kaydeder.
3. Telemetriden tepe ısı akısını çekip 600 karoluk gövde sektörünü inceler ve `pipeline_artifacts/tps_maintenance_work_order.md` iş emrini oluşturur.

---

## Modülleri Bağımsız Çalıştırma

Her alt paket kendi bağımsız CLI ve test araçlarına sahiptir:

```bash
# 1. starship-flip-gnc
cd starship-flip-gnc
python3 -m unittest discover -s tests
python3 -m starship_flip_gnc.cli --altitude 500.0 --vz -70.0 --export-json telemetry.json

# 2. starship-cryo-slosh
cd ../starship-cryo-slosh
python3 -m unittest discover -s tests
python3 -m starship_cryo_slosh.cli --telemetry ../starship-flip-gnc/telemetry.json --with-baffles

# 3. starship-tps-vision
cd ../starship-tps-vision
python3 -m unittest discover -s tests
python3 -m starship_tps_vision.cli --telemetry ../starship-flip-gnc/telemetry.json --export-markdown work_order.md
```

---

## Aviyonik ve Sistem Derleyicisi Entegrasyonu (Oxide)

Bu projedeki uçuş dinamiği ve kütle tüketim denklemleri, bağımsız C++20 Rust derleyicimiz **[Oxide (oxide-compiler)](https://github.com/isihussain/oxide-compiler)** ile entegre çalışacak şekilde tasarlanmıştır:

* **Sıfır Bağımlılıkla Freestanding C99:** `starship-flip-gnc` ve `starship-cryo-slosh` içindeki uçuş algoritmaları, Oxide'ın `StageMass` tipi ve kütle alt sınır doğrulamasıyla (`m_total >= m_dry`) derlenerek doğrudan gömülü aviyonik kartlarına ve radyasyon dayanımlı mikrodenetleyicilere (ARM, RISC-V, LEON) aktarılabilir.
* **Yüksek Başarımlı Uçuş Simülasyonu:** Oxide tarafından derlenen C99 kütüphaneleri, Python tarafına C-ABI (`ctypes`) üzerinden bağlanarak gerçek zamanlı simülasyon döngülerine dahil edilir.

---

## Katkı ve Lisans

Bu proje MIT lisansı altında yayımlanmıştır. Mühendisler depoları bağımsız olarak çatallayıp (fork) kendi itki, tank veya görüntü işleme modellerini ekleyebilir.

* **GitHub Sponsor:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Geliştirici Notu:** Bu projeyi 3 yıldır yerel Git ortamımda geliştiriyorum. Açık kaynak olarak yayımlama kararım, başka dünyalarda kalıcı insan yerleşimleri ve koloniler kurulmasını destekleme amacımdan kaynaklanıyor.
