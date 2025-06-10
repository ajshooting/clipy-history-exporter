# Clipy History Exporter

A tool to export all clipboard history saved in [Clipy](https://github.com/Clipy/Clipy), including images, into a single JSON file.

## Features

- One command handles everything from stopping Clipy to exporting, cleanup, and restarting.
- Processes a safe copy of the database without modifying the original.
- Exports text and images as Base64-encoded strings.

## Usage

1. Install dependencies:

```bash
pip3 install nska-deserialize
```

2. Grant execution permission:

```bash
chmod +x ./swift_helper/bin/RealmExporter
```

3. Run the script:

```bash
python3 export_clips.py
```

## For developers

```bash
cd swift_helper/src
swift build -c release
```
