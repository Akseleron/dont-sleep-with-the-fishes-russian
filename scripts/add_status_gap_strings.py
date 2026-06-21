from pathlib import Path
import csv

path = Path("translations/source_queue.tsv")

with path.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")
    fieldnames = reader.fieldnames
    rows = list(reader)

by_source = {r["source"]: r for r in rows}

def upsert(source, ru, context="status screenshot"):
    if source in by_source:
        r = by_source[source]
        r["final_russian"] = ru
        r["status"] = "approved"
        r["notes"] = "manual status gap"
    else:
        r = {k: "" for k in fieldnames}
        r["source"] = source
        r["context"] = context
        r["file"] = "manual_screenshot"
        r["kind"] = "manual_runtime"
        r["machine_russian"] = ""
        r["final_russian"] = ru
        r["status"] = "approved"
        r["notes"] = "manual status gap"
        rows.append(r)
        by_source[source] = r

upsert("I'm tired a bit", "Я немного устал")
upsert("I'm a little tired", "Я немного устал")
upsert("I am tired a bit", "Я немного устал")
upsert("I still have energy", "У меня ещё есть силы")
upsert("I'm full", "Я сыт")
upsert("I feel healthy", "Я здоров")

with path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

print("updated", path)
print("rows", len(rows))
