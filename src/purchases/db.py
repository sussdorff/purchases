"""SQLite database schema and operations for purchase tracking."""

import sqlite3
from pathlib import Path
from datetime import date
from decimal import Decimal
from typing import Iterator
from dataclasses import dataclass

from .config import get_db_path


@dataclass
class Item:
    """A purchased item."""
    id: int | None
    order_id: str
    vendor: str
    name: str
    price: Decimal
    currency: str
    quantity: int
    purchase_date: date
    category: str  # Our category
    vendor_category: str  # Amazon's category hierarchy
    vendor_sku: str  # ASIN or other vendor product ID
    order_url: str
    item_url: str
    is_digital: bool
    is_consumable: bool
    exported_to_vault: bool


# Our tracked categories
CATEGORIES = [
    "3d-printing",
    "games",
    "electronics",
    "clothing",
    "kitchen",
    "golf",
    "furniture",
    "rental-property",
    "smart-home",
    "tools",
    "other",
]


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    vendor TEXT NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'EUR',
    quantity INTEGER DEFAULT 1,
    purchase_date TEXT NOT NULL,
    category TEXT,
    vendor_category TEXT,
    vendor_sku TEXT,
    order_url TEXT,
    item_url TEXT,
    is_digital INTEGER DEFAULT 0,
    is_consumable INTEGER DEFAULT 0,
    exported_to_vault INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(order_id, vendor_sku, vendor)
);

CREATE INDEX IF NOT EXISTS idx_items_date ON items(purchase_date);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_vendor ON items(vendor);
CREATE INDEX IF NOT EXISTS idx_items_vendor_sku ON items(vendor_sku);
"""


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection, creating the DB if needed."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def insert_item(conn: sqlite3.Connection, item: Item, upsert: bool = False) -> tuple[int, str]:
    """Insert an item, returning (ID, action).

    Args:
        conn: Database connection
        item: Item to insert
        upsert: If True, update existing entries; if False, skip duplicates

    Returns:
        Tuple of (row_id, action) where action is 'inserted', 'updated', or 'skipped'
    """
    if upsert:
        # Check if exists
        cursor = conn.execute(
            "SELECT id FROM items WHERE order_id = ? AND vendor_sku = ? AND vendor = ?",
            (item.order_id, item.vendor_sku, item.vendor),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing
            conn.execute(
                """
                UPDATE items SET
                    name = ?, price = ?, currency = ?, quantity = ?,
                    purchase_date = ?, category = ?, vendor_category = ?,
                    order_url = ?, item_url = ?, is_digital = ?, is_consumable = ?
                WHERE id = ?
                """,
                (
                    item.name,
                    float(item.price),
                    item.currency,
                    item.quantity,
                    item.purchase_date.isoformat(),
                    item.category,
                    item.vendor_category,
                    item.order_url,
                    item.item_url,
                    int(item.is_digital),
                    int(item.is_consumable),
                    existing["id"],
                ),
            )
            conn.commit()
            return existing["id"], "updated"

    # Insert new (or skip if duplicate and not upsert)
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO items (
            order_id, vendor, name, price, currency, quantity,
            purchase_date, category, vendor_category, vendor_sku,
            order_url, item_url, is_digital, is_consumable
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.order_id,
            item.vendor,
            item.name,
            float(item.price),
            item.currency,
            item.quantity,
            item.purchase_date.isoformat(),
            item.category,
            item.vendor_category,
            item.vendor_sku,
            item.order_url,
            item.item_url,
            int(item.is_digital),
            int(item.is_consumable),
        ),
    )
    conn.commit()

    if cursor.lastrowid:
        return cursor.lastrowid, "inserted"
    return 0, "skipped"


def get_items_for_export(
    conn: sqlite3.Connection,
    min_price: float = 100.0,
    categories: list[str] | None = None,
) -> Iterator[Item]:
    """Get items that should be exported to the vault.

    Criteria: (matches category OR price >= min_price) AND NOT digital AND NOT consumable
    """
    cats = categories or [c for c in CATEGORIES if c != "other"]
    placeholders = ",".join("?" * len(cats))

    cursor = conn.execute(
        f"""
        SELECT * FROM items
        WHERE is_digital = 0
          AND is_consumable = 0
          AND exported_to_vault = 0
          AND (category IN ({placeholders}) OR price >= ?)
        ORDER BY purchase_date DESC
        """,
        (*cats, min_price),
    )

    for row in cursor:
        yield Item(
            id=row["id"],
            order_id=row["order_id"],
            vendor=row["vendor"],
            name=row["name"],
            price=Decimal(str(row["price"])),
            currency=row["currency"],
            quantity=row["quantity"],
            purchase_date=date.fromisoformat(row["purchase_date"]),
            category=row["category"],
            vendor_category=row["vendor_category"],
            vendor_sku=row["vendor_sku"],
            order_url=row["order_url"],
            item_url=row["item_url"],
            is_digital=bool(row["is_digital"]),
            is_consumable=bool(row["is_consumable"]),
            exported_to_vault=bool(row["exported_to_vault"]),
        )


def mark_exported(conn: sqlite3.Connection, item_id: int) -> None:
    """Mark an item as exported to the vault."""
    conn.execute(
        "UPDATE items SET exported_to_vault = 1 WHERE id = ?",
        (item_id,),
    )
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    """Get summary statistics."""
    cursor = conn.execute(
        """
        SELECT
            COUNT(*) as total_items,
            COUNT(DISTINCT order_id) as total_orders,
            SUM(price * quantity) as total_spent,
            COUNT(CASE WHEN exported_to_vault = 1 THEN 1 END) as exported,
            COUNT(CASE WHEN is_digital = 1 THEN 1 END) as digital,
            COUNT(CASE WHEN is_consumable = 1 THEN 1 END) as consumable
        FROM items
        """
    )
    row = cursor.fetchone()
    return dict(row)
