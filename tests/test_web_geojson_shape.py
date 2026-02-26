import json
from pathlib import Path


def _count_points(geometry: dict) -> int:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        return sum(len(ring) for ring in coords)
    if gtype == "MultiPolygon":
        return sum(len(ring) for polygon in coords for ring in polygon)
    return 0


def test_kr_adm1_geojson_contract_has_realistic_shape():
    path = Path("apps/web/public/geo/kr_adm1_simplified.geojson")
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])

    assert payload.get("type") == "FeatureCollection"
    assert len(features) == 17

    expected_codes = {
        "KR-11",
        "KR-21",
        "KR-22",
        "KR-23",
        "KR-24",
        "KR-25",
        "KR-26",
        "KR-29",
        "KR-31",
        "KR-32",
        "KR-33",
        "KR-34",
        "KR-35",
        "KR-36",
        "KR-37",
        "KR-38",
        "KR-39",
    }
    actual_codes = {feature.get("properties", {}).get("region_code") for feature in features}
    assert actual_codes == expected_codes

    # Reject placeholder rectangle maps by enforcing a minimum geometry complexity.
    point_count = sum(_count_points(feature.get("geometry", {})) for feature in features)
    assert point_count > 500
