"""Export items to Obsidian vault as Asset notes."""

import re
from pathlib import Path

from .db import Item
from .config import get_vault_path

ASSETS_FOLDER = "50-Databases/Assets"


def sanitize_filename(name: str) -> str:
    """Convert item name to a valid filename."""
    # Remove/replace invalid filename characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    # Collapse multiple spaces
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Trim to reasonable length (keep it readable)
    if len(sanitized) > 80:
        sanitized = sanitized[:77] + "..."
    return sanitized.strip()


def generate_asset_markdown(item: Item) -> str:
    """Generate markdown content for an asset note."""
    # Format price
    price_str = f"{item.price:.2f}" if item.price else ""

    # Build frontmatter
    frontmatter = f"""---
type: asset
name: "{item.name}"
category: {item.category}
purchase_date: {item.purchase_date.isoformat()}
price: {price_str}
currency: {item.currency}
vendor: {item.vendor}
vendor_sku: "{item.vendor_sku}"
order_id: "{item.order_id}"
warranty_until:
status: owned
product_url: "{item.item_url}"
---"""

    # Build body
    body = f"""
# {item.name}

## Notes


## Links
- [Product page]({item.item_url})
- [Order]({item.order_url})
"""

    return frontmatter + body


def export_item_to_vault(
    item: Item,
    vault_path: Path | None = None,
    dry_run: bool = False,
) -> Path:
    """Export a single item to the vault as a markdown file.

    Returns the path to the created file.
    """
    vault = vault_path or get_vault_path()
    if vault is None:
        raise ValueError("No vault path configured. Set VAULT_PATH environment variable.")

    assets_dir = vault / ASSETS_FOLDER

    # Ensure directory exists
    if not dry_run:
        assets_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    filename = sanitize_filename(item.name) + ".md"
    filepath = assets_dir / filename

    # Handle duplicates by appending vendor_sku
    if filepath.exists() and not dry_run:
        base = sanitize_filename(item.name)
        filename = f"{base} ({item.vendor_sku}).md"
        filepath = assets_dir / filename

    # Generate and write content
    content = generate_asset_markdown(item)

    if not dry_run:
        filepath.write_text(content, encoding="utf-8")

    return filepath


def export_items_to_vault(
    items: list[Item],
    vault_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Export multiple items to the vault.

    Returns stats about the export.
    """
    stats = {
        "total": len(items),
        "exported": 0,
        "skipped": 0,
        "files": [],
    }

    for item in items:
        try:
            filepath = export_item_to_vault(item, vault_path, dry_run)
            stats["exported"] += 1
            stats["files"].append(filepath)
        except Exception as e:
            print(f"Error exporting {item.name}: {e}")
            stats["skipped"] += 1

    return stats
