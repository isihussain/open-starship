# starship-cryo-slosh

Starship burun ve metan header tanklarındaki kriyojenik yakıt çalkantısını (slosh) ve iniş çevirme manevrası (landing flip) sırasındaki gaz yutma (ullage gas ingestion) riskini hesaplayan indirgenmiş mertebeli eşdeğer sarkaç simülatörü.

Uçuş kontrol sistemlerinin (GNC) ağır CFD çözümleri yerine gerçek zamanlı telemetri döngülerine entegre edebileceği şekilde NASA SP-106 hidrodinamik sarkaç formülasyonuyla inşa edilmiştir.

---

## Matematiksel Model

### 1. Eşdeğer Sarkaç Dinamiği (Abramson / Dodge Modeli)
Küresel tank içindeki serbest yüzey dalgalanması, sönümlü bir mekanik sarkaç diferansiyel denklemiyle ifade edilir:

$$\ddot{\phi} + 2 \zeta \omega_n \dot{\phi} + \frac{g_{eff}}{L_p} \sin(\phi - \phi_{eq}) = -\dot{\omega}_{vehicle}$$

Burada:
* $g_{eff} = \sqrt{a_{lateral}^2 + a_{axial}^2}$: Gövde koordinatlarında hissedilen bileşke ivme.
* $\phi_{eq} = \text{atan2}(a_{lateral}, a_{axial})$: Statik denge serbest yüzey açısı.
* $\omega_n = \sqrt{g_{eff} / L_p}$: Çalkantı doğal frekansı.
* $\zeta$: Hidrodinamik sönümleme oranı (halka dalgakıran yoksa $0.018$, dalgakıran varsa $0.085$).

### 2. Emiş Hattı Gaz Giriş Kriteri (Ullage Gas Ingestion)
Tank dip çıkışındaki emiş borusu üzerindeki anlık sıvı derinliği:

$$h_{submergence} = h_{nominal} - (R + z_{inlet}) - R |\sin(\phi)|$$

Eğer $h_{submergence} < h_{threshold}$ ($0.15\text{ m}$) olursa kütüphane motor turbopompası için kavitasyon/alev sönmesi (flameout) uyarısı üretir.

---

## Kurulum

```bash
cd starship-cryo-slosh
pip install -e .
```

---

## Hızlı Başlangıç

### CLI Kullanımı (starship-flip-gnc Telemetrisi ile)

```bash
python3 -m starship_cryo_slosh.cli --telemetry /yol/telemetry.json --with-baffles --export-json slosh_output.json
```

### Python API Kullanımı

```python
import json
from starship_cryo_slosh.tank import HeaderTankAssembly
from starship_cryo_slosh.simulator import SloshSimulator

# 1. Tank geometrisini olustur (istege bagli dalgakiran baffle destegi)
assembly = HeaderTankAssembly.default_starship(with_baffles=True)
sim = SloshSimulator(assembly=assembly, lox_mass_kg=17500.0, ch4_mass_kg=7500.0)

# 2. GNC modulunden cikan telemetriyi yukle
with open("flight_telemetry.json", "r") as f:
    telemetry_records = json.load(f)

# 3. Calkanti simulasyonunu calistir
result, history = sim.simulate_telemetry(telemetry_records)

print(f"Risk Seviyesi: {result.risk_level}")
print(f"LOX Gaz Alma Suresi: {result.lox_total_gas_exposure_time_s} s")
print(f"Maksimum Bozulma Torku: {result.max_slosh_torque_nm} N*m")
print(f"Maksimum Kütle Merkezi Sapmasi: {result.max_com_shift_x_mm} mm")
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
