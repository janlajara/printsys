import csv
import json

# Map your app label
APP_LABEL = "inventory"
MODEL_NAME = "item"

# Path to your CSV
csv_file = "utils/io/output.csv"
fixture_file = "utils/io/items_fixture.json"

fixture = []
pk_counter = 1

# Load categories and their attribute keys from database
from inventory.models import ItemCategory
category_map = {c.name: c.attributes for c in ItemCategory.objects.all()}
category_id_map = {c.name: c.id for c in ItemCategory.objects.all()}

# Machine categories that need name prepending
MACHINE_CATEGORIES = [
    "SORMZ Machine/Parts",
    "Minerva Machine/Parts",
    "KORS Machine/Parts",
    "GTO Machine/Parts",
]

# Define the CSV Category → ItemCategory mapping rules
def map_category(csv_category, csv_group):
    mapping = {
        "Special Paper": "Specialty Paper",
        "Board": "Paperboard",
        "Sticker": "Sticker Paper",
        "Carbonless Board": "Paperboard",
        "Carbonless Paper": "Carbonless Paper",
        "Ink": "Ink",
        "Films and Plates": "Films and Plates",
        "Finishing Materials": "Finishing Materials",
        "Maintenance Materials": "Maintenance Materials",
        "Machine Consumables": "Machine Consumables",
        "Chemicals": "Chemicals",
        "Envelope": "Envelope",
        "Folder": "Folder",
        "Others": "Others",
    }
    group_mapping = {
        "Machine and Parts": "Machines and Parts"
    }
    if csv_category in mapping:
        return mapping[csv_category]
    elif csv_group in group_mapping:
        return group_mapping[csv_group]
    else:
        return csv_group 

with open(csv_file, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        category_name = map_category(row["Category"], row["Group"])
        attributes_keys = category_map.get(category_name, [])
        attributes = {}

        for key in attributes_keys:
            # Fill attributes from CSV if present, else empty string
            if key in row:
                value = row[key]
                attributes[key] = value if value else ""
            else:
                attributes[key] = ""

        # Convert numeric pack quantity
        pack_qty = row.get("PackQty")
        try:
            pack_qty = int(pack_qty) if pack_qty else 1
        except ValueError:
            pack_qty = 1

        item_name = row["Type"] if row["Type"] else row["Category"]
        # Prepend machine name if category matches machine categories
        if row["Category"] in MACHINE_CATEGORIES:
            machine_name = row["Category"].split(" ")[0]  # Take the first word as machine name
            item_name = f"{machine_name} {item_name}"

        item = {
            "model": f"{APP_LABEL}.{MODEL_NAME}",
            "pk": pk_counter,
            "fields": {
                "name": item_name,
                "description": " ".join([f"{item_name}", *[x for x in attributes.values() if x]]),
                "category": category_id_map[category_name],
                "attributes": attributes,
                "individual_uom": row.get("IndUoM", "") or "",
                "pack_uom": row.get("PackUoM", "") or "",
                "pack_quantity": pack_qty
            }
        }
        fixture.append(item)
        pk_counter += 1

# Write to JSON fixture
with open(fixture_file, "w", encoding="utf-8") as f:
    json.dump(fixture, f, indent=4)

print(f"Fixture saved to {fixture_file}")
