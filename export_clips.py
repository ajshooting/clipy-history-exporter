import subprocess
import base64
import json
import time
import os
import sqlite3
import stat
import tempfile
from contextlib import closing, contextmanager
from importlib.resources import as_file, files
from nska_deserialize import deserialize_plist
from pathlib import Path


PACKAGE_NAME = "clipy_history_exporter"
REALM_EXPORTER_RELATIVE_PATH = Path("swift_helper/bin/RealmExporter")
OUTPUT_FILE = Path("./ClipyExport.json")
CLIPY_DATA_DIR = Path.home() / "Library/Application Support/com.clipy-app.Clipy"
CLIPY_SQLITE_PATH = CLIPY_DATA_DIR / "sqlite.db"

REQUIRED_SQLITE_TABLES = {
    "pasteboardHistories",
    "pasteboardHistoryAssets",
    "pasteboardHistoryThumbnailAssets",
}
TEXT_PASTEBOARD_TYPES = {
    "public.utf8-plain-text",
    "public.utf16-plain-text",
    "public.text",
    "NSStringPboardType",
    "public.url",
    "public.file-url",
    "NSURLPboardType",
}
IMAGE_PASTEBOARD_TYPES = {
    "public.png",
    "public.tiff",
    "public.jpeg",
    "com.adobe.pdf",
    "NSTIFFPboardType",
    "NSPDFPboardType",
}


def ensure_executable(path):
    if os.access(path, os.X_OK):
        return path

    try:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as e:
        raise PermissionError(f"RealmExporter is not executable: {path}") from e

    return path


@contextmanager
def realm_exporter_path():
    try:
        packaged_exporter = files(PACKAGE_NAME).joinpath("bin", "RealmExporter")
        if packaged_exporter.is_file():
            with as_file(packaged_exporter) as path:
                yield ensure_executable(path)
            return
    except ModuleNotFoundError:
        pass

    source_tree_exporter = Path(__file__).resolve().parent / REALM_EXPORTER_RELATIVE_PATH
    if not source_tree_exporter.exists():
        raise FileNotFoundError(
            "RealmExporter was not found. Reinstall the package or rebuild the Swift helper."
        )

    yield ensure_executable(source_tree_exporter)


def run_apple_script(script_string):
    try:
        subprocess.run(
            ["osascript", "-e", script_string], check=True, capture_output=True
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def manage_clipy_app(action):
    if action == "quit":
        print("Automatically quitting Clipy.app if it is running...")
        quit_script = 'tell application "System Events" to if (name of every process) contains "Clipy" then tell application "Clipy" to quit'
        run_apple_script(quit_script)
        time.sleep(2)
    elif action == "launch":
        print("Restarting Clipy.app...")
        launch_script = 'tell application "Clipy" to launch'
        run_apple_script(launch_script)


def readonly_sqlite_uri(database_path):
    path = Path(database_path).resolve()
    return f"{path.as_uri()}?mode=ro"


def has_current_sqlite_schema(database_path):
    if not database_path.exists():
        return False

    try:
        with closing(
            sqlite3.connect(readonly_sqlite_uri(database_path), uri=True)
        ) as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'virtual table')
                """
            ).fetchall()
    except (sqlite3.Error, OSError):
        return False

    table_names = {row[0] for row in rows}
    return REQUIRED_SQLITE_TABLES.issubset(table_names)


def copy_sqlite_database(source_path):
    fd, temp_path = tempfile.mkstemp(prefix="clipy_temp_copy_", suffix=".sqlite.db")
    os.close(fd)

    copied_path = Path(temp_path)
    try:
        with closing(
            sqlite3.connect(readonly_sqlite_uri(source_path), uri=True)
        ) as source_connection:
            with closing(sqlite3.connect(str(copied_path))) as copied_connection:
                source_connection.backup(copied_connection)
    except Exception:
        if copied_path.exists():
            copied_path.unlink()
        raise

    return copied_path


def parse_pasteboard_types(raw_value):
    if not raw_value:
        return []

    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return []

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, str)]

    return []


def decode_text_data(data, pasteboard_type=None):
    if data is None:
        return None
    if isinstance(data, str):
        return data
    if not isinstance(data, (bytes, bytearray, memoryview)):
        return None

    raw_data = bytes(data)
    encodings = ["utf-8", "utf-16", "utf-16-le", "utf-16-be"]

    if isinstance(pasteboard_type, str):
        normalized_type = pasteboard_type.lower().replace("-", "")
        if "utf16" in normalized_type:
            encodings = ["utf-16", "utf-16-le", "utf-16-be", "utf-8"]
        elif "utf8" in normalized_type:
            encodings = ["utf-8", "utf-16", "utf-16-le", "utf-16-be"]

    for encoding in encodings:
        try:
            text = raw_data.decode(encoding).strip("\x00")
        except UnicodeDecodeError:
            continue

        if encoding == "utf-8" and "\x00" in text:
            continue
        if text:
            return text

    return None


def is_text_pasteboard_type(pasteboard_type):
    if not isinstance(pasteboard_type, str):
        return False

    return (
        pasteboard_type in TEXT_PASTEBOARD_TYPES
        or "plain-text" in pasteboard_type
        or pasteboard_type.startswith("public.text")
    )


def is_image_pasteboard_type(pasteboard_type):
    if not isinstance(pasteboard_type, str):
        return False

    return (
        pasteboard_type in IMAGE_PASTEBOARD_TYPES
        or pasteboard_type.startswith("public.image")
    )


def extract_sqlite_content(assets):
    text_content = None
    image_data = None
    image_type = None

    for pasteboard_type, data in assets:
        if text_content is None and is_text_pasteboard_type(pasteboard_type):
            text_content = decode_text_data(data, pasteboard_type)

        if (
            image_data is None
            and is_image_pasteboard_type(pasteboard_type)
            and isinstance(data, (bytes, bytearray, memoryview))
        ):
            image_data = bytes(data)
            image_type = pasteboard_type

        if text_content is not None and image_data is not None:
            break

    image_data_base64 = None
    if image_data is not None:
        image_data_base64 = base64.b64encode(image_data).decode("utf-8")

    return text_content, image_data_base64, image_type


def count_sqlite_histories(database_path):
    with closing(sqlite3.connect(str(database_path))) as connection:
        return connection.execute("SELECT COUNT(*) FROM pasteboardHistories").fetchone()[0]


def build_sqlite_clip_entry(history, assets, database_path):
    pasteboard_types = parse_pasteboard_types(history["pasteboardTypes"])
    if not pasteboard_types:
        pasteboard_types = [pasteboard_type for pasteboard_type, _ in assets]

    text_content, image_data_base64, image_type = extract_sqlite_content(assets)
    primary_type = pasteboard_types[0] if pasteboard_types else ""

    return {
        "dataHash": history["id"],
        "dataPath": None,
        "title": history["title"],
        "primaryType": primary_type,
        "updateTime": history["updateAt"],
        "thumbnailPath": None,
        "isColorCode": history["thumbnailKind"] == "colorCode",
        "copiedRealmPath": None,
        "copiedSQLitePath": str(database_path),
        "pasteboardTypes": pasteboard_types,
        "deviceID": history["deviceID"],
        "textContent": text_content,
        "imageData_base64": image_data_base64,
        "image_uti": image_type,
    }


def iter_sqlite_clip_entries(database_path):
    connection = sqlite3.connect(str(database_path))
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
              h.id,
              h.title,
              h.pasteboardTypes,
              h.deviceID,
              h.updateAt,
              t.kind AS thumbnailKind,
              a.pasteboardType AS assetPasteboardType,
              a.data AS assetData
            FROM pasteboardHistories h
            LEFT JOIN pasteboardHistoryThumbnailAssets t
              ON t.pasteboardHistoryID = h.id
            LEFT JOIN pasteboardHistoryAssets a
              ON a.pasteboardHistoryID = h.id
            ORDER BY h.updateAt DESC, h.id DESC, a."index" ASC
            """
        )

        current_history = None
        current_assets = []

        for row in rows:
            if current_history is not None and row["id"] != current_history["id"]:
                yield build_sqlite_clip_entry(
                    current_history,
                    current_assets,
                    database_path,
                )
                current_assets = []

            current_history = row
            if row["assetPasteboardType"] is not None:
                current_assets.append((row["assetPasteboardType"], row["assetData"]))

        if current_history is not None:
            yield build_sqlite_clip_entry(
                current_history,
                current_assets,
                database_path,
            )
    finally:
        connection.close()


def iter_legacy_realm_clip_entries(metadata_list):
    for meta in metadata_list:
        data_path = Path(meta["dataPath"])
        if not data_path.is_absolute():
            data_path = CLIPY_DATA_DIR / data_path.name

        if not data_path.exists():
            continue

        clip_entry = meta.copy()
        (
            clip_entry["textContent"],
            clip_entry["imageData_base64"],
            clip_entry["image_uti"],
        ) = (None, None, None)

        try:
            with open(data_path, "rb") as data_f:
                deserialized_data = deserialize_plist(data_f)
        except Exception:
            continue

        string_content, image_data = None, None
        if isinstance(deserialized_data, dict) and "$objects" in deserialized_data:
            objects = deserialized_data["$objects"]
            string_content = next(
                (
                    obj
                    for obj in objects
                    if isinstance(obj, str) and len(obj) > 1
                ),
                None,
            )
            for obj in objects:
                if isinstance(obj, dict) and "NS.data" in obj:
                    image_data = obj["NS.data"]
                    break
        elif isinstance(deserialized_data, str):
            string_content = deserialized_data
        elif isinstance(deserialized_data, dict):
            for value in deserialized_data.values():
                if isinstance(value, str) and not string_content:
                    string_content = value
                elif isinstance(value, bytes) and not image_data:
                    image_data = value

        if string_content:
            clip_entry["textContent"] = string_content
        if image_data:
            clip_entry["imageData_base64"] = base64.b64encode(image_data).decode("utf-8")
            clip_entry["image_uti"] = meta.get("primaryType", "")

        yield clip_entry


def write_json_entries(entries, total_items):
    written_items = 0
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("[\n")
        for clip_entry in entries:
            if written_items > 0:
                f.write(",\n")

            json.dump(clip_entry, f, indent=2, ensure_ascii=False)
            written_items += 1

            if written_items % 1000 == 0:
                print(f"Progress: {written_items}/{total_items} items completed")

        f.write("\n]\n")

    if written_items == 0 or written_items % 1000 != 0:
        print(f"Progress: {written_items}/{total_items} items completed")

    return written_items


def load_legacy_realm_metadata():
    print("\nRunning Swift helper to safely copy the Realm DB and retrieve metadata...")
    with realm_exporter_path() as exporter_path:
        result = subprocess.run(
            [str(exporter_path)], capture_output=True, text=True, check=True
        )
    return json.loads(result.stdout)


def main():
    copied_database_path = None

    try:
        manage_clipy_app("quit")

        if has_current_sqlite_schema(CLIPY_SQLITE_PATH):
            print("\nDetected current Clipy SQLite database schema.")
            print("Copying SQLite DB and reading history assets...")
            copied_database_path = copy_sqlite_database(CLIPY_SQLITE_PATH)
            total_items = count_sqlite_histories(copied_database_path)
            entry_iter = iter_sqlite_clip_entries(copied_database_path)
        else:
            metadata_list = load_legacy_realm_metadata()
            if not metadata_list:
                print("No clip information found, terminating process.")
                return
            copied_database_path = metadata_list[0].get("copiedRealmPath")
            total_items = len(metadata_list)
            entry_iter = iter_legacy_realm_clip_entries(metadata_list)

        if total_items == 0:
            print("No clip information found, terminating process.")
            return

        print(f"Retrieved {total_items} clip information entries.")
        print("\nDecoding each clip and starting streaming write to file...")
        written_items = write_json_entries(entry_iter, total_items)

        print("\nExport completed!")
        print(f"Output location: {OUTPUT_FILE.resolve()}")
        if written_items != total_items:
            print(f"Warning: Exported {written_items}/{total_items} readable items.")

    except Exception as e:
        print(f"Error: A critical error occurred: {e}")

    finally:
        if copied_database_path and os.path.exists(copied_database_path):
            try:
                os.remove(copied_database_path)
                print("\nCleanup: Temporary file deleted.")
            except Exception as e:
                print(f"Warning: Failed to delete temporary file: {e}")

        manage_clipy_app("launch")


if __name__ == "__main__":
    main()
