import json
import sys
from pathlib import Path
from jsonschema import validate, ValidationError

root = Path(__file__).resolve().parents[1]
schema_path = root / "schemas" / "job.schema.json"

if len(sys.argv) != 2:
    print("ERROR: Bitte Pfad zu einer Job-JSON angeben.")
    sys.exit(1)

job_path = Path(sys.argv[1])

try:
    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    job = json.loads(job_path.read_text(encoding="utf-8-sig"))
    validate(instance=job, schema=schema)
    print(f"VALID: {job['job_id']} | {job['job_type']} | {job['quantity']}")
except FileNotFoundError as e:
    print(f"ERROR: Datei nicht gefunden: {e.filename}")
    sys.exit(1)
except ValidationError as e:
    print(f"INVALID: {e.message}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
