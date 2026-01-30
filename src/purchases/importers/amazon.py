"""Import Amazon order history from CSV export."""

import csv
import re
from pathlib import Path
from datetime import date
from decimal import Decimal
from typing import Iterator

from ..db import Item, CATEGORIES


# Map Amazon category patterns to our categories
CATEGORY_MAPPING = [
    # Order matters - first match wins
    (r"Homematic|Smart Home", "smart-home"),
    (r"3D.*Drucker|Filament|SUNLU|CNC KITCHEN", "3d-printing"),
    (r"Sports.*Golf|Golf", "golf"),
    (r"DIY & Tools|Power.*Tool|Hand Tools|Drill|Bosch Professional", "tools"),
    (r"Electronics|TV.*Video|Headphones|Computer|HDMI|Apple.*Pods", "electronics"),
    (r"Kitchen.*Appliances|Fryer|Knife|Waterdrop", "kitchen"),
    (r"Furniture|Desk|Chair", "furniture"),
    (r"Fashion|Clothing|Shoes|T-Shirt|Sneaker|Socken", "clothing"),
    (r"Toys|Games|Spielzeug|Puzzle", "games"),
]

# Patterns for digital items (exclude from vault)
DIGITAL_PATTERNS = [
    r"Audible",
    r"Kindle",
    r"eBook",
    r"Digital.*Download",
    r"gp/video/detail",  # Video purchases (URL pattern)
    r"digi_order_details",  # Digital order URL pattern
]

# Patterns for consumables (exclude from vault)
CONSUMABLE_PATTERNS = [
    r"Battery|Batterie|Alkaline",
    r"Toothbrush.*Head|Aufsteckbürst",
    r"Shampoo|Duschgel|Lotion|Seife|Handcreme",
    r"Magnesium|Vitamin",
    r"Interdentalbürst",
    r"Rasiergel",
    r"Feuerzeuggas",
    r"Gin|Whisky|Spirits",  # Alcohol
    r"Grocery|Beer.*Wine.*Spirits",
]


def _parse_price(price_str: str) -> Decimal:
    """Parse price string like '€123.45' or '€1,284.69' to Decimal."""
    if not price_str:
        return Decimal("0")
    # Remove currency symbol and whitespace
    cleaned = re.sub(r"[€$£\s]", "", price_str)
    # Handle European format (1.234,56) vs US format (1,234.56)
    # Amazon DE uses €1,284.69 format (comma for thousands in display, but CSV has dot)
    cleaned = cleaned.replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def _map_category(name: str, vendor_category: str) -> str:
    """Map item to our category based on name and vendor category."""
    combined = f"{name} {vendor_category}"
    for pattern, category in CATEGORY_MAPPING:
        if re.search(pattern, combined, re.IGNORECASE):
            return category
    return "other"


def _is_digital(name: str, item_url: str, vendor_category: str) -> bool:
    """Check if item is digital (should be excluded from vault)."""
    combined = f"{name} {item_url} {vendor_category}"
    return any(re.search(p, combined, re.IGNORECASE) for p in DIGITAL_PATTERNS)


def _is_consumable(name: str, vendor_category: str) -> bool:
    """Check if item is consumable (should be excluded from vault)."""
    combined = f"{name} {vendor_category}"
    return any(re.search(p, combined, re.IGNORECASE) for p in CONSUMABLE_PATTERNS)


def parse_amazon_items_csv(csv_path: Path) -> Iterator[Item]:
    """Parse Amazon items CSV and yield Item objects.

    Expected columns: order id, order url, order date, quantity, description,
                     item url, price, subscribe & save, ASIN, category
    """
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Skip empty rows or header duplicates
            order_id = row.get("order id", "").strip()
            if not order_id or order_id == "order id":
                continue

            name = row.get("description", "").strip()
            if not name:
                continue

            vendor_category = row.get("category", "").strip()
            item_url = row.get("item url", "").strip()
            order_url = row.get("order url", "").strip()

            # Parse date
            date_str = row.get("order date", "").strip()
            try:
                purchase_date = date.fromisoformat(date_str)
            except ValueError:
                continue

            # Parse price and quantity
            price = _parse_price(row.get("price", ""))
            try:
                quantity = int(row.get("quantity", "1") or "1")
            except ValueError:
                quantity = 1

            yield Item(
                id=None,
                order_id=order_id,
                vendor="amazon",
                name=name,
                price=price,
                currency="EUR",
                quantity=quantity,
                purchase_date=purchase_date,
                category=_map_category(name, vendor_category),
                vendor_category=vendor_category,
                vendor_sku=row.get("ASIN", "").strip(),
                order_url=order_url,
                item_url=item_url,
                is_digital=_is_digital(name, item_url, vendor_category),
                is_consumable=_is_consumable(name, vendor_category),
                exported_to_vault=False,
            )


def import_amazon_items(csv_path: Path, conn, upsert: bool = False) -> dict:
    """Import Amazon items CSV into the database.

    Args:
        csv_path: Path to the CSV file
        conn: Database connection
        upsert: If True, update existing entries; if False, skip duplicates

    Returns stats about the import.
    """
    from ..db import insert_item

    stats = {
        "total": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "digital": 0,
        "consumable": 0,
        "by_category": {},
    }

    for item in parse_amazon_items_csv(csv_path):
        stats["total"] += 1

        if item.is_digital:
            stats["digital"] += 1
        if item.is_consumable:
            stats["consumable"] += 1

        # Track by category
        cat = item.category
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        # Insert or update
        _, action = insert_item(conn, item, upsert=upsert)
        stats[action] += 1

    return stats
