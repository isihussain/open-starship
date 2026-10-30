# starship-tps-vision

Starship gövdesindeki 18.000'den fazla altıgen seramik termal koruma karosunun (TPS) uçuş sonrası muayenesini yapan, aerotermal uçuş yük haritasıyla hasarları önceliklendiren açık kaynak muayene hattı.

Gövde üzerindeki eksik, çatlak, kenarı kırılmış karoları ve plazma sızıntısına yol açabilecek aralık genleşmelerini tespit ederek yer bakım ekipleri için acil parça değişim iş emirleri üretir.

---

## Mimarisi ve Uçuş Verisi Köprüsü

```
[ starship-flip-gnc Telemetrisi ]
             │ (Tepe Isı Akısı & Dinamik Basınç)
             ▼
   [ AerothermalRiskMap ]
             │ (Gövde Bölgesel Risk Ağırlığı: w_risk)
             ▼
[ Kamera / Sensör Karo Gözlemleri ] ──> [ TileDefectDetector ]
                                                │
                                                ▼
                                    [ Sıralı Bakım İş Emri (JSON / MD) ]
```

### Kusur Sınıflandırma Kriterleri:
1. **MISSING_TILE:** Yüzey alanı kaybı $> \%80$ (karo tamamen kopmuş, paslanmaz çelik gövde açıkta).
2. **CRACKED_TILE:** Çatlak uzunluğu $\ge 20.0\text{ mm}$ (seramik gövdede kırılma riski).
3. **EXPANDED_GAP:** Karolar arası boşluk $> 4.5\text{ mm}$ (nominal $2.0\text{ mm}$, plazma sızıntı riski).
4. **CHIPPED_EDGE:** Kenar/köşe kırığı (alan kaybı $\%6$ ile $\%20$ arası).

Öncelik Skoru = $\text{Temel Şiddet} \times w_{risk}$. En yüksek termal ve akustik yüke maruz kalan burun ve kanatçık menteşe bölgelerindeki hasarlar bakım listesinde en üste alınır.

---

## Kurulum

```bash
cd starship-tps-vision
pip install -e .
```

---

## Hızlı Başlangıç

### CLI Kullanımı

```bash
python3 -m starship_tps_vision.cli \
  --telemetry /yol/telemetry.json \
  --tiles-axial 30 \
  --tiles-azimuthal 20 \
  --defect-rate 0.05 \
  --export-json tps_report.json \
  --export-markdown tps_work_order.md
```

### Python API Kullanımı

```python
from starship_tps_vision.thermal_map import AerothermalRiskMap
from starship_tps_vision.synthetic import SyntheticTileGridGenerator
from starship_tps_vision.detector import TileDefectDetector
from starship_tps_vision.reporter import InspectionReporter

# 1. Telemetriden aerotermal risk haritasini kur
risk_map = AerothermalRiskMap(peak_heat_flux_w_m2=150000.0, peak_q_dyn_pa=40000.0)

# 2. Karo gozlemlerini al
generator = SyntheticTileGridGenerator()
observations = generator.generate_sector(num_tiles_axial=20, num_tiles_azimuthal=15, defect_rate=0.08)

# 3. Denetle ve onceliklendir
detector = TileDefectDetector(risk_map=risk_map)
batch = detector.inspect_batch(observations)

print(f"Toplam Denetlenen: {batch.total_inspected}")
print(f"Acil Degisim Gereken: {batch.critical_replacements_required}")

# 4. Rapor uret
InspectionReporter.generate_markdown_report(batch, "work_order.md")
```

---

## Testleri Çalıştırma

```bash
python3 -m unittest discover -s tests
```

---

## Sponsor ve Katkı

Projeyi desteklemek ve geliştirmelere katkı sağlamak için:
- **GitHub Sponsor:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Geliştirici Notu:** Bu projeyi 3 yıldır yerel Git ortamımda geliştiriyorum. Açık kaynak olarak yayımlama kararım, başka dünyalarda kalıcı insan yerleşimleri ve koloniler kurulmasını destekleme amacımdan kaynaklanıyor.
