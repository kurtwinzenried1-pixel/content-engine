import json
from pathlib import Path
from jsonschema import validate, ValidationError

root = Path(__file__).resolve().parents[1]
schema_path = root / "schemas" / "brand-profile.schema.json"
brand_path = root / "storage" / "JOB-0001-brand.json"

try:
    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    brand = json.loads(brand_path.read_text(encoding="utf-8-sig"))
    validate(instance=brand, schema=schema)
    print(f"VALID BRAND: {brand['company']} | {brand['industry']} | {brand['language']}")
except ValidationError as e:
    print(f"INVALID BRAND: {e.message}")
    raise SystemExit(1)
except Exception as e:
    print(f"ERROR: {e}")
    raise SystemExit(1)
