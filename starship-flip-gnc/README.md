# starship-flip-gnc

Starship yatay gövde düşüşünden (belly-flop) dikey inişe geçiş (landing flip) manevrasını modelleyen 3 serbestlik dereceli (3-DoF) yörünge optimizasyonu ve itki vektör kontrol (TVC) kütüphanesi.

Manevra, 3 adet Raptor 3 motorunun ateşlenmesi, 90 derecelik ani rotasyon torku, 2 motorlu yüksek ivmeli frenleme ve tek motorlu son temas yakımı aşamalarını fiziksel sınır şartlarıyla çözer.

---

## Matematiksel Model ve Dinamik Denklemler

### 1. Öteleme Hareketi
İtki vektörü gövde açısı $\theta$ ve gimbal sapması $\delta$ ile tanımlanır:

$$F_{T,x} = F_T \sin(\theta - \delta)$$

$$F_{T,z} = F_T \cos(\theta - \delta)$$

Toplam ivmeler yerçekimi ($g = 9.80665 \text{ m/s}^2$) ve aerodinamik kuvvetler ($F_{drag}, F_{lift}$) bileşkesinden hesaplanır:

$$a_x = \frac{F_{T,x} + F_{aero,x}}{m(t)}, \quad a_z = \frac{F_{T,z} + F_{aero,z} - m(t)g}{m(t)}$$

### 2. Dönme Dinamiği
Motor gimbal mafsalı ağırlık merkezinin $19.0\text{ m}$ arkasındadır. Üretilen yunuslama (pitch) momenti:

$$M_{net} = -F_T \sin(\delta) \cdot r_{gimbal} - c_{rot} q_{dyn} A_{broad} L \omega$$

Açısal ivme $\alpha_{ang} = M_{net} / I_{yy}$ formülüyle 4. mertebe Runge-Kutta (RK4) entegratörüne verilir.

---

## Kurulum

Harici bağımlılık gerektirmez. Saf Python 3.9+ ile çalışır:

```bash
cd starship-flip-gnc
pip install -e .
```

---

## Hızlı Başlangıç

### Komut Satırından Simülasyon Çalıştırma

```bash
python3 -m starship_flip_gnc.cli --altitude 500.0 --vz -70.0 --export-json telemetry.json --export-csv telemetry.csv
```

### Python API Kullanımı

```python
from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger

vehicle = StarshipVehicle(dry_mass=100000.0, landing_propellant_mass=25000.0)
optimizer = TrajectoryOptimizer(vehicle=vehicle)
logger = TelemetryLogger()

initial_state = FlightState(z=500.0, vz=-70.0)
result = optimizer.simulate(initial_state=initial_state, dt=0.02, logger=logger)

print(f"Basari: {result.success}")
print(f"Inis Suresi: {result.touchdown_time_s} s | Kalan Yakit: {result.propellant_remaining_kg} kg")

# Telemetriyi disa aktar (starship-cryo-slosh ve starship-tps-vision girdi dosyasi)
logger.export_json("flight_telemetry.json")
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
