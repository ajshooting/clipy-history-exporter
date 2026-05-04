# Clipy History Exporter

A tool to export all clipboard history saved in [Clipy](https://github.com/Clipy/Clipy), including images, into a single JSON file.

## Features

- One command handles everything from stopping Clipy to exporting, cleanup, and restarting.
- Processes a safe copy of the database without modifying the original.
- Exports text and images as Base64-encoded strings.

## Usage

Run directly with `uvx`:

```bash
uvx --from git+https://github.com/ajshooting/clipy-history-exporter@main clipy-history-exporter
```

The command writes `ClipyExport.json` to the current directory.

### Manual usage from a release archive

1. Download the latest release:

Visit the [Releases page](https://github.com/ajshooting/clipy-history-exporter/releases/latest) and download and unzip it.

2. Install dependencies:

```bash
pip3 install nska-deserialize
```

3. Grant execution permission:

```bash
chmod +x ./swift_helper/bin/RealmExporter
```

4. Run the script:

```bash
python3 export_clips.py
```

## For developers

Build the Python package:

```bash
uv build
```

The bundled `swift_helper/bin/RealmExporter` binary is updated on `main` by the `Update bundled RealmExporter` GitHub Actions workflow. Run that workflow after changing the Swift helper source, then commit only the Python/package changes locally.

The release workflow also builds a fresh universal `RealmExporter` for release archives.
