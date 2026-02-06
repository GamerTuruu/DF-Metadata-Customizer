# Quick Reference - CLI Advanced Filtering

## Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Contains (default) | `title=Lady` |
| `==` | Exact match | `artist==Lady Gaga` |
| `!=` | Not equal | `version!=1` |
| `>` | Greater than | `version>2` |
| `<` | Less than | `version<3` |
| `>=` | Greater or equal | `disc>=2` |
| `<=` | Less or equal | `track<=10` |
| `=latest` | Latest version only | `version=latest` |
| `!=latest` | Not latest version | `version!=latest` |

## All Available Metadata Fields

- `title` - Song title
- `artist` - Original artist name  
- `coverartist` - Cover artist name
- `version` - Version number
- `date` - Release date
- `disc` - Disc number
- `track` - Track number
- `special` - Special tag (0 or 1)
- `comment` - Comments

## Usage

```bash
# Basic syntax
df-metadata-customizer apply <folder> <preset> --filter "<query>"

# Short flag
df-metadata-customizer apply <folder> <preset> -f "<query>"

# With dry-run (preview changes)
df-metadata-customizer apply <folder> <preset> --filter "version>=2" --dry-run
```

## Common Recipes

### Get specific cover artist versions
```bash
df-metadata-customizer apply ./songs Default -f "coverartist=Neuro"
```

### Apply to latest versions only
```bash
df-metadata-customizer apply ./songs Default -f "version=latest"
```

### Disc numbering filter
```bash
df-metadata-customizer apply ./songs Default -f "disc>=2"
```

### Multiple version check
```bash
# Version between 2 and 3 (requires two commands or manual selection)
df-metadata-customizer apply ./songs Default -f "version>=2"
df-metadata-customizer apply ./songs Default -f "version<3"
```

### Exact matches with quotes
```bash
df-metadata-customizer apply ./songs Default -f 'title="Never Gonna Give You Up"'
```

## Advanced Examples

### Track from specific disc
First filter by disc, then in UI you can further refine:
```bash
df-metadata-customizer apply ./songs Default -f "disc==2"
```

### Not equal filter
```bash
df-metadata-customizer apply ./songs Default -f "special!=1"
```

### Version preview before applying
```bash
df-metadata-customizer apply ./songs Default -f "version=latest" --dry-run
```

---

**Note:** Simple text search (without operators) searches across Title, Artist, CoverArtist, Special, and Version fields.
