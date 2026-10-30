# Devam Notu (Open-Starship Projesi)

Bu belge, projeyi devralacak veya sürdürecek geliştiriciler için mimari kararları, çalışma ortamı talimatlarını ve sıradaki kilometre taşlarını açıklar.

---

## 1. Proje Amacı ve Kapsamı
Starship mimarisinin üç temel fiziksel darboğazı modellenmiştir:
1. **starship-flip-gnc:** Yatay düşüşten dikey inişe geçiş (landing flip) yörünge optimizasyonu ve itki vektör kontrolü.
2. **starship-cryo-slosh:** 90 derecelik ani yönelim esnasında burun ve metan header tanklarındaki kriyojenik yakıt çalkantısı, kütle merkezi kayması ve emiş borusu gaz alma riski.
3. **starship-tps-vision:** Uçuş aerotermal yük haritasını girdi alarak gövde seramik karolarındaki kırılma, ayrılma ve çatlakları önceliklendiren muayene hattı.

## 2. Modüller Arası Veri Köprüsü
```
[ starship-flip-gnc ]
       │
       │ (JSON telemetri: t, x, z, vx, vz, theta, omega, a_lateral, a_axial, q_heat)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[ starship-cryo-slosh ]               [ starship-tps-vision ]
  - Çalkantı bozulma momenti            - Termal risk haritası
  - CoM sapması                         - Hasarlı karo tespiti
  - Gaz yutma uyarısı                   - Kritik muayene raporu
```

## 4. Proje Durumu ve GitHub Dağıtım Adımları
Projedeki 3 modül bağımsız paketler olarak tasarlanmıştır. GitHub'da iki farklı şekilde yayımlanabilir:
1. **Tek Monorepo (Önerilen İlk Aşama):** `open-starship` adında tek bir repo açıp tüm alt dizinleri ve `run_pipeline.py` orkestratörünü tek bir çatı altında paylaşmak.
2. **Organizasyon Altında 3 Ayrı Repo:** `open-starship` adında bir GitHub Organization kurup:
   - `github.com/open-starship/starship-flip-gnc`
   - `github.com/open-starship/starship-cryo-slosh`
   - `github.com/open-starship/starship-tps-vision`
   şeklinde 3 ayrı repository olarak yayımlamak. Bu durumda her alt klasör birer Git reposu olarak başlatılıp (`git init`) push edilir.

## 5. Doğrulama ve Test Komutları
```bash
# Tüm testleri çalıştırma:
cd /Users/johndoe/.gemini/antigravity/scratch/open-starship
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-flip-gnc/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-cryo-slosh/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-tps-vision/tests

# Uçtan uca boru hattını çalıştırma:
python3 run_pipeline.py pipeline_artifacts
```

## 6. Gelecek Geliştirme Önerileri
- **starship-flip-gnc:** 6-DoF gövde dinamikleri ve aerodinamik flap kontrol yüzeylerinin (grid fins / body flaps) bağımsız aerodinamik moment türevlerini eklemek.
- **starship-cryo-slosh:** Çok modlu (multi-mode) sarkaç modeli veya düşük çözünürlüklü SPH (Smoothed Particle Hydrodynamics) çözücüsü eklemek.
- **starship-tps-vision:** Drone kameralarından çekilen gerçek Starship fırlatma kulesi fotoğrafları üzerinde YOLOv8 / SAM entegrasyonu için PyTorch ağırlık dosyalarını repoya bağlamak.
