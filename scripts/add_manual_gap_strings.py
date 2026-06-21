from pathlib import Path
import csv

path = Path("translations/source_queue.tsv")

with path.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")
    fieldnames = reader.fieldnames
    rows = list(reader)

if not fieldnames:
    raise SystemExit("No TSV header found")

by_source = {r["source"]: r for r in rows}


def upsert(source, ru, context, kind="manual_runtime", notes="manual screenshot gap"):
    if source in by_source:
        r = by_source[source]
        r["final_russian"] = ru
        r["status"] = "approved"
        r["notes"] = notes
    else:
        r = {k: "" for k in fieldnames}
        r["source"] = source
        r["context"] = context
        r["file"] = "manual_screenshot"
        r["kind"] = kind
        r["machine_russian"] = ""
        r["final_russian"] = ru
        r["status"] = "approved"
        r["notes"] = notes
        rows.append(r)
        by_source[source] = r


# Journal exact lines from screenshots
upsert(
    "Well, there goes Dorothy...",
    "Ну вот и Дороти...",
    "journal screenshot",
)

upsert(
    "Row’ and I are the only ones left, sitting in this old junk of a lifeboat.",
    "Мы с Роу остались одни в этой старой развалине спасательной шлюпки.",
    "journal screenshot",
)

upsert(
    "I have no idea what struck our ship, and judging by the sound, I honestly don’t want to find out.",
    "Понятия не имею, что ударило по нашему кораблю, и, судя по звуку, честно говоря, не хочу это выяснять.",
    "journal screenshot",
)

upsert(
    "Now all we can do is survive as long as we need. I’m sure help will come soon.",
    "Теперь нам остаётся только выживать столько, сколько потребуется. Уверен, помощь скоро придёт.",
    "journal screenshot",
)

# Possible whole journal block variants
upsert(
    "Well, there goes Dorothy...\n\nRow’ and I are the only ones left, sitting in this old junk of a lifeboat.\n\nI have no idea what struck our ship, and judging by the sound, I honestly don’t want to find out.\n\nNow all we can do is survive as long as we need. I’m sure help will come soon.",
    "Ну вот и Дороти...\n\nМы с Роу остались одни в этой старой развалине спасательной шлюпки.\n\nПонятия не имею, что ударило по нашему кораблю, и, судя по звуку, честно говоря, не хочу это выяснять.\n\nТеперь нам остаётся только выживать столько, сколько потребуется. Уверен, помощь скоро придёт.",
    "journal screenshot multiline",
)

upsert(
    "Well, there goes Dorothy...<br>Row’ and I are the only ones left, sitting in this old junk of a lifeboat.<br>I have no idea what struck our ship, and judging by the sound, I honestly don’t want to find out.<br>Now all we can do is survive as long as we need. I’m sure help will come soon.",
    "Ну вот и Дороти...<br>Мы с Роу остались одни в этой старой развалине спасательной шлюпки.<br>Понятия не имею, что ударило по нашему кораблю, и, судя по звуку, честно говоря, не хочу это выяснять.<br>Теперь нам остаётся только выживать столько, сколько потребуется. Уверен, помощь скоро придёт.",
    "journal screenshot br",
)

# Dialogue exact strings
upsert(
    "... Why did you choose me?",
    "... Почему ты выбрал меня?",
    "dialogue screenshot",
)

upsert(
    ".. I'm not sold on the idea that all this was a coincidence.",
    ".. Не верится мне, что всё это было совпадением.",
    "dialogue screenshot",
)

# HUD exact strings without exclamation marks
upsert("I'm full", "Я сыт", "hud screenshot")
upsert("I still have energy", "У меня ещё есть силы", "hud screenshot")
upsert("I feel healthy", "Я здоров", "hud screenshot")

# Friend panel
upsert("Row", "Роу", "friend panel")
upsert("Happy", "Счастлив", "friend panel")

with path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

print("updated", path)
print("rows", len(rows))
