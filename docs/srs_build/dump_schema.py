import json, sys
sys.path.insert(0, ".")
from app.database.models import *
from app.database.connection import Base
out = {}
for t in Base.metadata.sorted_tables:
    cols = []
    for c in t.columns:
        cols.append({"name": c.name, "type": str(c.type), "pk": c.primary_key, "null": c.nullable,
                     "fk": [f.target_fullname for f in c.foreign_keys], "unique": bool(c.unique)})
    out[t.name] = cols
json.dump(out, open("../docs/srs_build/schema.json", "w"), indent=1)
for k, v in out.items():
    print(k, len(v), [c["name"] for c in v if c["fk"]])
