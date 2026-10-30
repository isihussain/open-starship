# starship-tps-vision

An automated inspection and defect prioritization pipeline for the 18,000+ hexagonal ceramic Thermal Protection System (TPS) tiles on the Starship hull.

Fuses aerothermal flight loading maps with optical measurements to identify missing tiles, ceramic cracks, chipped borders, and plasma-leak gap expansions, generating prioritized maintenance work orders for launch turnaround crews.

---

## Architecture & Flight Load Bridge

```
[ starship-flip-gnc Telemetry ]
             │ (Peak Heat Flux & Dynamic Pressure)
             ▼
   [ AerothermalRiskMap ]
             │ (Hull Zonal Risk Multiplier: w_risk)
             ▼
[ Camera / Sensor Tile Observations ] ──► [ TileDefectDetector ]
                                                │
                                                ▼
                                    [ Prioritized Work Order (Markdown/JSON) ]
```

### Defect Classification Rules:
1. **MISSING_TILE:** Surface area loss $> 80\%$ (tile detached, stainless steel hull exposed).
2. **CRACKED_TILE:** Transverse structural fracture length $\ge 20.0\text{ mm}$.
3. **EXPANDED_GAP:** Inter-tile clearance $> 4.5\text{ mm}$ (nominal $2.0\text{ mm}$, plasma blow-through hazard).
4. **CHIPPED_EDGE:** Corner/perimeter spallation ($6\%$ to $20\%$ surface area loss).

Priority Score = $\text{Base Severity} \times w_{risk}$. Defects located in high convective heating (nose stagnation cap) or high acoustic vibration (flap hinges and engine skirt) zones receive prioritized scheduling.

---

## Installation

```bash
cd starship-tps-vision
pip install -e .
```

---

## Quickstart

### CLI Usage

```bash
python3 -m starship_tps_vision.cli \
  --telemetry /path/to/telemetry.json \
  --tiles-axial 30 \
  --tiles-azimuthal 20 \
  --defect-rate 0.05 \
  --export-json tps_report.json \
  --export-markdown tps_work_order.md
```

### Python API

```python
from starship_tps_vision.thermal_map import AerothermalRiskMap
from starship_tps_vision.synthetic import SyntheticTileGridGenerator
from starship_tps_vision.detector import TileDefectDetector
from starship_tps_vision.reporter import InspectionReporter

# 1. Initialize aerothermal risk map from flight loads
risk_map = AerothermalRiskMap(peak_heat_flux_w_m2=150000.0, peak_q_dyn_pa=40000.0)

# 2. Acquire tile sensor observations
generator = SyntheticTileGridGenerator()
observations = generator.generate_sector(num_tiles_axial=20, num_tiles_azimuthal=15, defect_rate=0.08)

# 3. Classify and rank maintenance priority
detector = TileDefectDetector(risk_map=risk_map)
batch = detector.inspect_batch(observations)

print(f"Total Inspected: {batch.total_inspected}")
print(f"Critical Replacements Required: {batch.critical_replacements_required}")

# 4. Generate maintenance work order
InspectionReporter.generate_markdown_report(batch, "work_order.md")
```

---

## Running Tests

```bash
python3 -m unittest discover -s tests
```

---

## Contributing & Support

* **GitHub Sponsors:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Developer Note:** I have developed this project over the past 3 years in my local Git environment. My decision to publish it as open source is driven by my commitment to supporting the establishment of permanent human colonies and settlements on other worlds.
