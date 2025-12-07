import csv

INPUT_FILE = "io/input.csv"
OUTPUT_FILE = "io/output.csv"

# Columns to extract
FIELDS = [
    "Group", "Category", "Type", "Brand", "Texture", "Color",
    "Thickness", "Size", "MinStockQty",
    "IndUoM", "PackUoM", "PackQty"
]

# Columns to capitalize first letter
CAPITALIZE_FIELDS = ["Type", "Brand", "Texture", "Color"]

# Columns to lowercase
LOWERCASE_FIELDS = ["IndUoM", "PackUoM", "PackQty"]


def capitalize_preserve_acronym(value: str) -> str:
    if not value:
        return ""
    # If all letters are uppercase, assume acronym → keep as is
    if value.isupper():
        return value
    # Otherwise, capitalize first letter only
    return value[0].upper() + value[1:].lower()


def format_value(field, value):
    if value is None:
        return ""
    value = value.strip()
    #if field in CAPITALIZE_FIELDS and value:
    #    return capitalize_preserve_acronym(value)
    if field in LOWERCASE_FIELDS and value:
        return value.lower()
    return value


def transform_csv(input_file, output_file):
    with open(input_file, newline="", encoding="utf-8") as infile, \
         open(output_file, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=FIELDS)

        writer.writeheader()

        for row in reader:
            # Skip rows where Category is empty or None
            if not row.get("Category"):
                continue

            # Extract only the required fields
            filtered_row = {field: row.get(field, "").strip() for field in FIELDS}

            # Rule: If PackQty is 9999 → clear PackQty and PackUoM
            pack_qty = row.get("PackQty")
            if pack_qty and pack_qty.strip() in ["99", "999", "9999"]:
                filtered_row["PackQty"] = ""
                filtered_row["PackUoM"] = ""

            # Apply formatting rules
            for field in FIELDS:
                filtered_row[field] = format_value(field, filtered_row[field])

            writer.writerow(filtered_row)


if __name__ == "__main__":
    transform_csv(INPUT_FILE, OUTPUT_FILE)
    print(f"CSV transformed and saved to {OUTPUT_FILE}")
