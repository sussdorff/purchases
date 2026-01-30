"""CLI for purchase tracking."""

import argparse
import shutil
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from .config import get_db_path, get_vault_path, get_resolved_config
from .db import get_db, get_stats, get_items_for_export, mark_exported, search_items, CATEGORIES
from .importers import import_amazon_items
from .exporter import export_item_to_vault


def cmd_config(args):
    """Show resolved configuration."""
    config = get_resolved_config()

    print("Purchases Configuration:")
    print(f"  Database:     {config['db_path']}")
    print(f"                {'(exists)' if config['db_exists'] else '(not created yet)'}")
    print(f"  Data dir:     {config['data_dir']}")
    print(f"  Config dir:   {config['config_dir']}")

    if config['vault_path']:
        print(f"  Vault:        {config['vault_path']}")
        print(f"                {'(exists)' if config['vault_exists'] else '(not found)'}")
    else:
        print("  Vault:        (not configured)")

    # Show active environment overrides
    overrides = {k: v for k, v in config['env_overrides'].items() if v}
    if overrides:
        print("\nEnvironment overrides:")
        for key, value in overrides.items():
            print(f"  {key}={value}")


def cmd_migrate(args):
    """Migrate database from another location."""
    source = Path(args.source)
    if not source.exists():
        print(f"Error: Source database not found: {source}", file=sys.stderr)
        sys.exit(1)

    dest = get_db_path()

    if dest.exists() and not args.force:
        print(f"Error: Destination already exists: {dest}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # Ensure parent directory exists
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Copy the database
    shutil.copy2(source, dest)
    print(f"Migrated database from {source} to {dest}")

    # Show stats
    conn = get_db(dest)
    stats = get_stats(conn)
    print(f"\nDatabase contains:")
    print(f"  {stats['total_items']} items in {stats['total_orders']} orders")


def cmd_import(args):
    """Import purchases from a source."""
    conn = get_db()

    if args.source == "amazon":
        if not args.file:
            print("Error: --file required for Amazon import", file=sys.stderr)
            sys.exit(1)
        csv_path = Path(args.file)
        if not csv_path.exists():
            print(f"Error: File not found: {csv_path}", file=sys.stderr)
            sys.exit(1)

        stats = import_amazon_items(csv_path, conn, upsert=args.update)

        print("Imported from Amazon CSV:")
        print(f"  Total items:    {stats['total']}")
        print(f"  New items:      {stats['inserted']}")
        print(f"  Updated:        {stats['updated']}")
        print(f"  Skipped:        {stats['skipped']}")
        print(f"  Digital:        {stats['digital']}")
        print(f"  Consumable:     {stats['consumable']}")
        print("\nBy category:")
        for cat, count in sorted(stats["by_category"].items()):
            print(f"  {cat}: {count}")
    else:
        print(f"Error: Unknown source: {args.source}", file=sys.stderr)
        sys.exit(1)


def cmd_stats(args):
    """Show database statistics."""
    conn = get_db()
    stats = get_stats(conn)

    print("Purchase Database Statistics:")
    print(f"  Total items:    {stats['total_items']}")
    print(f"  Total orders:   {stats['total_orders']}")
    print(f"  Total spent:    EUR {stats['total_spent']:.2f}" if stats['total_spent'] else "  Total spent:    EUR 0.00")
    print(f"  Exported to vault: {stats['exported']}")
    print(f"  Digital (skip vault): {stats['digital']}")
    print(f"  Consumable (skip vault): {stats['consumable']}")


def cmd_search(args):
    """Search purchases with filters."""
    conn = get_db()

    # Parse date arguments
    on_date = date.fromisoformat(args.date) if args.date else None
    amount = Decimal(args.amount) if args.amount else None
    from_date = date.fromisoformat(args.from_date) if args.from_date else None
    to_date = date.fromisoformat(args.to_date) if args.to_date else None

    items = list(search_items(
        conn,
        on_date=on_date,
        amount=amount,
        from_date=from_date,
        to_date=to_date,
    ))

    if not items:
        print("No matching items found.")
        return

    print(f"Found {len(items)} matching items:\n")
    for item in items:
        print(f"  [{item.category}] {item.name[:60]}")
        print(f"    EUR {item.price} | {item.purchase_date} | {item.vendor}")
        print()


def cmd_list(args):
    """List items pending export."""
    conn = get_db()

    items = list(get_items_for_export(conn, min_price=args.min_price))
    if not items:
        print("No items pending export.")
        return

    print(f"Items pending export ({len(items)}):\n")
    for item in items:
        print(f"  [{item.category}] {item.name[:60]}")
        print(f"    EUR {item.price} | {item.purchase_date} | {item.vendor}")
        print()


def cmd_export(args):
    """Export items to Obsidian vault."""
    conn = get_db()
    vault_path = Path(args.vault) if args.vault else get_vault_path()

    if vault_path is None:
        print("Error: No vault configured. Set VAULT_PATH or use --vault.", file=sys.stderr)
        sys.exit(1)

    # Get items to export
    items = list(get_items_for_export(conn, min_price=args.min_price))
    if not items:
        print("No items pending export.")
        return

    print(f"Found {len(items)} items to export to {vault_path}")

    if args.dry_run:
        print("\nDry run - would export:")
        for item in items:
            print(f"  [{item.category}] {item.name[:60]}")
        return

    # Confirm unless --yes
    if not args.yes:
        response = input(f"\nExport {len(items)} items? [y/N] ")
        if response.lower() != "y":
            print("Aborted.")
            return

    # Export each item
    exported = 0
    for item in items:
        try:
            filepath = export_item_to_vault(item, vault_path)
            mark_exported(conn, item.id)
            exported += 1
            print(f"  + {filepath.name}")
        except Exception as e:
            print(f"  x {item.name[:50]}: {e}", file=sys.stderr)

    print(f"\nExported {exported}/{len(items)} items to {vault_path / '50-Databases/Assets'}")


def main():
    parser = argparse.ArgumentParser(
        prog="purchases",
        description="Purchase history tracking",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # config command
    p_config = subparsers.add_parser("config", help="Show resolved configuration")
    p_config.set_defaults(func=cmd_config)

    # migrate command
    p_migrate = subparsers.add_parser("migrate", help="Migrate database from another location")
    p_migrate.add_argument("source", help="Path to source database file")
    p_migrate.add_argument(
        "--force", "-f", action="store_true",
        help="Overwrite existing database"
    )
    p_migrate.set_defaults(func=cmd_migrate)

    # import command
    p_import = subparsers.add_parser("import", help="Import purchases from a source")
    p_import.add_argument("source", choices=["amazon"], help="Import source")
    p_import.add_argument("--file", "-f", help="Path to import file")
    p_import.add_argument(
        "--update", "-u", action="store_true",
        help="Update existing entries instead of skipping duplicates"
    )
    p_import.set_defaults(func=cmd_import)

    # stats command
    p_stats = subparsers.add_parser("stats", help="Show database statistics")
    p_stats.set_defaults(func=cmd_stats)

    # search command
    p_search = subparsers.add_parser("search", help="Search purchases with filters")
    p_search.add_argument(
        "--date", "-d",
        help="Search by exact date (YYYY-MM-DD)"
    )
    p_search.add_argument(
        "--amount", "-a",
        help="Search by exact amount (e.g., 365.95)"
    )
    p_search.add_argument(
        "--from", dest="from_date",
        help="Start of date range (YYYY-MM-DD)"
    )
    p_search.add_argument(
        "--to", dest="to_date",
        help="End of date range (YYYY-MM-DD)"
    )
    p_search.set_defaults(func=cmd_search)

    # list command
    p_list = subparsers.add_parser("list", help="List items pending export")
    p_list.add_argument(
        "--min-price", type=float, default=100.0,
        help="Minimum price for 'other' category items (default: 100)"
    )
    p_list.set_defaults(func=cmd_list)

    # export command
    p_export = subparsers.add_parser("export", help="Export items to Obsidian vault")
    p_export.add_argument(
        "--min-price", type=float, default=100.0,
        help="Minimum price for 'other' category items (default: 100)"
    )
    p_export.add_argument(
        "--vault", "-v",
        help="Path to Obsidian vault"
    )
    p_export.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be exported without creating files"
    )
    p_export.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt"
    )
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
