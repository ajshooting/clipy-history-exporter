# Clipy History Exporter

A tool to export all clipboard history saved in [Clipy](https://github.com/Clipy/Clipy), including images, into a single JSON file.

## Features

- One command handles everything from stopping Clipy to exporting, cleanup, and restarting.
- Automatically detects the current SQLite-backed Clipy history schema and falls back to the legacy Realm-backed schema