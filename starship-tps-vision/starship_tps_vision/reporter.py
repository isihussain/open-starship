"""
Inspection reporting and maintenance work order generation.
"""

from pathlib import Path
import json
from typing import Dict, Any

from .detector import InspectionBatchResult


class InspectionReporter:
    """
    Exports TPS inspection findings to structured JSON and Markdown work orders.
    """

    @staticmethod
    def export_json(batch_result: InspectionBatchResult, file_path: str, indent: int = 2) -> None:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(batch_result.to_dict(), f, indent=indent)

    @staticmethod
    def generate_markdown_report(batch_result: InspectionBatchResult, file_path: str) -> str:
        """
        Creates a clean Markdown work order for ground maintenance crews.
        """
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Starship TPS Karo Muayene ve Bakım Raporu",
            "",
            "## Özet İstatistikler",
            f"- **Toplam Denetlenen Karo:** {batch_result.total_inspected}",
            f"- **Kusursuz / Sağlam:** {batch_result.intact_count}",
            f"- **Kusurlu Karo Sayısı:** {batch_result.defective_count}",
            f"- **Acil Değişim Gerektiren (Kritik):** {batch_result.critical_replacements_required}",
            "",
            "### Hasar Dağılımı",
            f"- Eksik / Düşmüş Karolar: {batch_result.missing_count}",
            f"- Yapısal Çatlak Karolar: {batch_result.cracked_count}",
            f"- Kenar / Köşe Kırıkları: {batch_result.chipped_count}",
            f"- Aralık Genleşmesi (Plazma Riski): {batch_result.gap_expansion_count}",
            "",
            "## Öncelikli Değişim Listesi (Kritik ve Yüksek Öncelik)",
            "",
            "| Sıra | Karo ID | Bölge | İrtifa (z) | Azimut | Kusur Türü | Öncelik Skoru | Bakım Aksiyonu |",
            "|---|---|---|---|---|---|---|---|",
        ]

        # Filter only defective tiles, top priority first:
        defective_tiles = [r for r in batch_result.results if r.severity_level in ("CRITICAL", "HIGH", "MEDIUM")]

        if not defective_tiles:
            lines.append("| - | Yok | - | - | - | Kusur Bulunmadı | 0.0 | Uçuşa Hazır |")
        else:
            for idx, tile in enumerate(defective_tiles[:30], 1):
                lines.append(
                    f"| {idx} | `{tile.tile_id}` | {tile.zone_id} | {tile.z_hull_m:.2f}m | "
                    f"{tile.azimuth_deg:.1f}° | **{tile.detected_defect.value}** | "
                    f"`{tile.priority_score:.1f}` ({tile.severity_level}) | `{tile.action_required}` |"
                )

        lines.extend([
            "",
            "---",
            "Bu rapor, uçuş telemetrisindeki aerotermal yük dağılımı ile yer muayene verilerinin birleşimiyle üretilmiştir.",
        ])

        content = "\n".join(lines)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

        return content
