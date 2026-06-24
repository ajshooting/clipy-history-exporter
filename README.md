# Clipy History Exporter

A tool to export all clipboard history saved in [Clipy](https://github.com/Clipy/Clipy), including images, into a single JSON file.

## Features

- One command handles everything from stopping Clipy to exporting, cleanup, and restarting.
- Automatically detects the current SQLite-backed Clipy history schema and falls back to the legacy Realm-backed schema.
- Processes a safe copy of the database without modifying the original.
- Exports text and images as Base64-encoded strings.

## Usage

Run directly with uvx:

    uvx --from git+https://github.com/ajshooting/clipy-history-exporter@main clipy-history-exporter

The command writes ClipyExport.json to the current directory.

### Manual usage from a release archive

1. Download the latest release from the Releases page.
2. Install dependencies:

    pip3 install nska-deserialize

3. Grant execution permission for the legacy Realm helper:

    chmod +x ./swift_helper/bin/RealmExporter

4. Run the script:

    python3 export_clips.py

## For developers

Build the Python package:

    uv build

The bundled swift_helper/bin/RealmExporter binary is only used for legacy Realm-backed histories. Current SQLite-backed histories are read directly by Python.

The release workflow also builds a fresh universal RealmExporter for release archives.
