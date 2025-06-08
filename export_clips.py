import subprocess
import base64
import json
import time
import os
from nska_deserialize import deserialize_plist
from pathlib import Path


REALM_EXPORTER_PATH = "./swift_helper/bin/RealmExporter"
OUTPUT_FILE = Path("./ClipyExport.json")
CLIPY_DATA_DIR = Path.home() / "Library/Application Support/com.clipy-app.Clipy"


def run_apple_script(script_string):
    try:
        subprocess.run(
            ["osascript", "-e", script_string], check=True, capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
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


def main():

    copied_realm_path = None

    manage_clipy_app("quit")

    try:
        print("\nRunning Swift helper to safely copy the DB and retrieve metadata...")
        result = subprocess.run(
            [REALM_EXPORTER_PATH], capture_output=True, text=True, check=True
        )
        metadata_list = json.loads(result.stdout)

        if not metadata_list:
            print("No clip information found, terminating process.")
            return

        print(f"Retrieved {len(metadata_list)} clip information entries.")
        copied_realm_path = metadata_list[0].get("copiedRealmPath")

        print("\nDecoding each clip and starting streaming write to file...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("[\n")
            total_items = len(metadata_list)
            for i, meta in enumerate(metadata_list):
                # (このループの中身は変更なし)
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
                if (
                    isinstance(deserialized_data, dict)
                    and "$objects" in deserialized_data
                ):
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
                    clip_entry["imageData_base64"] = base64.b64encode(
                        image_data
                    ).decode("utf-8")
                    clip_entry["image_uti"] = meta.get("primaryType", "")

                json.dump(clip_entry, f, indent=2, ensure_ascii=False)

                if i < total_items - 1:
                    f.write(",\n")

                if (i + 1) % 1000 == 0 or (i + 1) == total_items:
                    print(f"Progress: {i+1}/{total_items} items completed")

            f.write("\n]\n")

        print("\nExport completed!")
        print(f"Output location: {OUTPUT_FILE.resolve()}")

    except Exception as e:
        print(f"Error: A critical error occurred: {e}")

    finally:
        if copied_realm_path and os.path.exists(copied_realm_path):
            try:
                os.remove(copied_realm_path)
                print("\nCleanup: Temporary file deleted.")
            except Exception as e:
                print(f"Warning: Failed to delete temporary file: {e}")

        manage_clipy_app("launch")


if __name__ == "__main__":
    main()
