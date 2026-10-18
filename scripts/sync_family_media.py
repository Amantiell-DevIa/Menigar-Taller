#!/usr/bin/env python3
"""Verify the four representative home-card images against MENIGAR's public archive.

The three BMW images reuse files already cached for their service pages. Only
the ABS example is copied from its published WordPress URL. No cropping or
retouching is applied, so file hashes continue to identify the source bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/wordpress_exports/2026-10-13-publico/main"
MANIFEST = ROOT / "data/family-media-manifest.json"

# The source page is evidence of where this example was shown, not evidence
# that it is compatible with all vehicles in the broad family.
SELECTIONS = [
    {
        "family": "cuadro",
        "localPath": "/assets/bmw/107ed09aaed6-bmw_serie-3_f30_display.jpg",
        "sourceUrl": "https://www.menigar.com/wp-content/uploads/2021/09/bmw_serie-3_f30_display.jpg",
        "sourcePage": "https://www.menigar.com/reparacion-cuadro-instrumentos/bmw/serie-3/",
        "sourcePageId": 512,
        "wordpressMediaId": 8752,
        "sha256": "528183ea643fc2d91f7331cde36b4c3b106e0a9dd6ea13c2adee535a707914d2",
        "width": 640,
        "height": 480,
        "alt": "Ejemplo de cuadro de instrumentos BMW Serie 3 F30 publicado por MENIGAR.",
        "suggestedFit": "cover",
        "suggestedPosition": "center 56%",
    },
    {
        "family": "abs",
        "localPath": "/assets/family/abs-citroen-ate-mk70.jpg",
        "sourceUrl": "https://www.menigar.com/wp-content/uploads/2023/02/abs_ate_mk70.jpg",
        "sourcePage": "https://www.menigar.com/reparacion-fallo-abs-c1380-citroen-ate-mk70/",
        "sourcePageId": 13299,
        "wordpressMediaId": 13301,
        "sha256": "376a20802988f2a69fdcb95b114399917f52c451fbbfa834649c57b3c581a1bc",
        "width": 300,
        "height": 300,
        "alt": "Ejemplo de módulo ABS ATE MK70 mostrado en una ficha de Citroën de MENIGAR.",
        "suggestedFit": "contain",
        "suggestedPosition": "center",
    },
    {
        "family": "display",
        "localPath": "/assets/bmw/aa76d38fccf4-display_bmw_serie1.jpg",
        "sourceUrl": "https://www.menigar.com/wp-content/uploads/2021/09/display_bmw_serie1.jpg",
        "sourcePage": "https://www.menigar.com/reparacion-displays/reparacion-display-bmw/",
        "sourcePageId": 2321,
        "wordpressMediaId": 8693,
        "sha256": "a732e3fc2176b44cf6f066912a4627abde5755e385ef41d7cd11c18da0d173d6",
        "width": 640,
        "height": 480,
        "alt": "Ejemplo de display de un cuadro BMW Serie 1 publicado por MENIGAR.",
        "suggestedFit": "cover",
        "suggestedPosition": "center 48%",
    },
    {
        "family": "multimedia",
        "localPath": "/assets/bmw/d18e0b972ece-multimedia_bmw_x5_e70.jpg",
        "sourceUrl": "https://www.menigar.com/wp-content/uploads/2022/05/multimedia_bmw_x5_e70.jpg",
        "sourcePage": "https://www.menigar.com/reparacion-pantalla-tactil-multimedia/bmw-connecteddrive/",
        "sourcePageId": 8973,
        "wordpressMediaId": 10767,
        "sha256": "ad4df3fe328785dcb9d76db1b34cf831ef0e86355c0390b904d7b8636f693c84",
        "width": 640,
        "height": 480,
        "alt": "Ejemplo de pantalla multimedia BMW X5 E70 publicada por MENIGAR.",
        "suggestedFit": "cover",
        "suggestedPosition": "center 52%",
    },
]

# A wider, documentary option for the ABS card. WordPress identifies this as
# ABS repair media but does not link it to a specific repair page or vehicle.
ABS_WORKSHOP_ALTERNATIVE = {
    "family": "abs",
    "localPath": "/assets/family/abs-taller-menigar.jpg",
    "sourceUrl": "https://www.menigar.com/wp-content/uploads/2017/12/reparacion_abs_menigar3.jpg",
    "sourceAttachment": "https://www.menigar.com/reparacion_abs_menigar3/",
    "sourcePage": None,
    "sourceVariant": None,
    "wordpressMediaId": 1948,
    "sha256": "8b972361de3c383bad81ef5a7c6731a93f9e81fb1b6db8a693b11ad044301e7c",
    "width": 640,
    "height": 480,
    "alt": "Técnico de MENIGAR trabajando sobre un módulo ABS en el taller.",
    "suggestedFit": "cover",
    "suggestedPosition": "center 58%",
    "usageNote": "Fotografía de taller clasificada como reparación ABS por WordPress; ninguna ficha o variante concreta quedó asociada en el archivo público.",
}

# Distinct documentary images from the 2017 public archive. Their upload date
# is recorded so they cannot accidentally be presented as current facilities.
WORKSHOP_EVIDENCE = [
    {
        "subject": "banco de comprobación de cuadro",
        "localPath": "/assets/family/taller-banco-cuadro-archivo-2017.jpg",
        "sourceUrl": "https://www.menigar.com/wp-content/uploads/2017/04/taller_menigar04.jpg",
        "sourceAttachment": "https://www.menigar.com/taller_menigar04/",
        "wordpressMediaId": 159,
        "wordpressUploadedAt": "2017-04-20T15:07:39",
        "sha256": "628ae783355278c6595141773a9d939eabe83e0d568eed642aa2888fa90a1e16",
        "width": 941,
        "height": 628,
        "alt": "Archivo de MENIGAR: técnico comprobando un cuadro de instrumentos en un banco de trabajo.",
        "usageNote": "Imagen histórica subida a WordPress en 2017; no acredita el estado actual de las instalaciones.",
    },
    {
        "subject": "inspección de electrónica",
        "localPath": "/assets/family/taller-revision-ecu-archivo-2017.jpg",
        "sourceUrl": "https://www.menigar.com/wp-content/uploads/2017/04/rep_ecu.jpg",
        "sourceAttachment": "https://www.menigar.com/rep_ecu/",
        "wordpressMediaId": 156,
        "wordpressUploadedAt": "2017-04-20T15:07:36",
        "sha256": "79fdc1b42bd9b60ff51ea28df6276a2c49dd89f593c5bc6bbc4d895c8ea1093a",
        "width": 1024,
        "height": 768,
        "alt": "Archivo de MENIGAR: técnica inspeccionando una placa electrónica en el banco de trabajo.",
        "usageNote": "Imagen histórica subida a WordPress en 2017; no acredita el estado actual de las instalaciones.",
    },
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archived_records(kind: str) -> dict[int, dict]:
    records = {}
    for page in sorted((ARCHIVE / kind).glob("page-*.json")):
        items = json.loads(page.read_text(encoding="utf-8"))
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("id"), int):
                    records[item["id"]] = item
    return records


def verify_archive() -> None:
    media = archived_records("media")
    pages = archived_records("pages")
    bmw_manifest = json.loads((ROOT / "data/bmw-media-manifest.json").read_text(encoding="utf-8"))
    bmw_by_id = {item["wordpressMediaId"]: item for item in bmw_manifest["files"]}
    for choice in SELECTIONS:
        media_record = media[choice["wordpressMediaId"]]
        assert media_record["source_url"] == choice["sourceUrl"], choice["family"]
        detail = media_record["media_details"]
        assert (detail["width"], detail["height"]) == (choice["width"], choice["height"]), choice["family"]
        page = pages[choice["sourcePageId"]]
        assert page["link"] == choice["sourcePage"], choice["family"]
        content = page["content"]["rendered"]
        # WordPress may render the 300x225 variant in page HTML while the
        # archive stores the original. The filename stem identifies both.
        assert Path(choice["sourceUrl"]).stem in content, choice["family"]
        if choice["family"] != "abs":
            cached = bmw_by_id[choice["wordpressMediaId"]]
            assert cached["downloadUrl"] == choice["sourceUrl"], choice["family"]
            assert cached["localPath"] == choice["localPath"], choice["family"]
            assert cached["sha256"] == choice["sha256"], choice["family"]
    alternative_media = media[ABS_WORKSHOP_ALTERNATIVE["wordpressMediaId"]]
    assert alternative_media["source_url"] == ABS_WORKSHOP_ALTERNATIVE["sourceUrl"]
    assert alternative_media["link"] == ABS_WORKSHOP_ALTERNATIVE["sourceAttachment"]
    details = alternative_media["media_details"]
    assert (details["width"], details["height"]) == (
        ABS_WORKSHOP_ALTERNATIVE["width"], ABS_WORKSHOP_ALTERNATIVE["height"]
    )
    for photo in WORKSHOP_EVIDENCE:
        record = media[photo["wordpressMediaId"]]
        assert record["source_url"] == photo["sourceUrl"]
        assert record["link"] == photo["sourceAttachment"]
        assert record["date"] == photo["wordpressUploadedAt"]
        dimensions = record["media_details"]
        assert (dimensions["width"], dimensions["height"]) == (photo["width"], photo["height"])


def download_if_needed(choice: dict) -> None:
    target = ROOT / choice["localPath"].lstrip("/")
    if target.exists():
        return
    request = Request(choice["sourceUrl"], headers={"User-Agent": "Mozilla/5.0 (MENIGAR local media archive)"})
    with urlopen(request, timeout=30) as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "image/jpeg"
        data = response.read(2_000_001)
    assert len(data) <= 2_000_000 and data.startswith(b"\xff\xd8\xff")
    assert hashlib.sha256(data).hexdigest() == choice["sha256"], "ABS source changed; review before reuse"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def main() -> None:
    verify_archive()
    download_if_needed(next(item for item in SELECTIONS if item["family"] == "abs"))
    download_if_needed(ABS_WORKSHOP_ALTERNATIVE)
    for photo in WORKSHOP_EVIDENCE:
        download_if_needed(photo)
    for choice in [*SELECTIONS, ABS_WORKSHOP_ALTERNATIVE, *WORKSHOP_EVIDENCE]:
        local = ROOT / choice["localPath"].lstrip("/")
        assert local.is_file(), choice["localPath"]
        assert digest(local) == choice["sha256"], f"Source file changed: {choice['localPath']}"
    manifest = {
        "purpose": "Representative home-card images for repair families; examples, not compatibility claims",
        "wordpressArchive": "2026-10-13-publico",
        "usageNote": "The vehicle/part pictured is one published example. Product compatibility requires review of the customer's reference and fault.",
        "cards": SELECTIONS,
        "alternativeAbs": ABS_WORKSHOP_ALTERNATIVE,
        "workshopArchivePhotos": WORKSHOP_EVIDENCE,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Verified 4 card images, 1 ABS alternative and 2 workshop archive photos; wrote", MANIFEST.relative_to(ROOT))


if __name__ == "__main__":
    main()
