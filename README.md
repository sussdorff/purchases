# purchases

Purchase history tracking CLI with SQLite storage and Obsidian vault export.

## Features

- Import purchase history from Amazon order exports
- Categorize items (electronics, tools, kitchen, etc.)
- Filter digital and consumable items
- Export qualifying items to Obsidian vault as Asset notes
- XDG/macOS-compliant configuration paths

## Installation

```bash
# With uv
uv tool install git+https://github.com/mroethli/purchases

# Or clone and install locally
git clone https://github.com/mroethli/purchases
cd purchases
uv sync
```

## Usage

### Show configuration

```bash
purchases config
```

Shows resolved paths for database, config directory, and vault.

### Import Amazon orders

Export your Amazon order history as CSV, then:

```bash
purchases import amazon -f ~/Downloads/amazon-orders.csv
```

Use `-u` to update existing entries instead of skipping duplicates.

### View statistics

```bash
purchases stats
```

### List items pending export

```bash
purchases list
purchases list --min-price 50  # Lower threshold for "other" category
```

### Export to Obsidian vault

```bash
purchases export --dry-run    # Preview what would be exported
purchases export -y           # Export without confirmation
purchases export -v /path/to/vault  # Specify vault path
```

### Migrate existing database

If you have an existing database from another location:

```bash
purchases migrate /path/to/old/purchases.db
```

## Configuration

The tool uses platform-specific paths via `platformdirs`:

| Platform | Data Directory |
|----------|---------------|
| macOS    | `~/Library/Application Support/purchases/` |
| Linux    | `~/.local/share/purchases/` |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `PURCHASES_DB_PATH` | Direct path to SQLite database file |
| `PURCHASES_DATA_DIR` | Directory for data files |
| `PURCHASES_CONFIG_DIR` | Directory for config files |
| `VAULT_PATH` | Path to Obsidian vault root |

## Item Categories

Items are auto-categorized based on name and Amazon category:

- `3d-printing` - 3D printers, filament, accessories
- `electronics` - Computers, headphones, cables
- `tools` - Power tools, hand tools
- `kitchen` - Appliances, cookware
- `smart-home` - Home automation devices
- `golf` - Golf equipment
- `games` - Toys, puzzles, games
- `clothing` - Apparel, shoes
- `furniture` - Desks, chairs
- `rental-property` - Items for rental properties
- `other` - Everything else

## Export Criteria

Items are exported to the vault if:
- Not digital (e-books, streaming, etc.)
- Not consumable (batteries, toiletries, etc.)
- Either in a tracked category OR price >= threshold (default EUR 100)

## License

MIT
