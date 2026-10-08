"""Validate local ESPImageServer packages and prepare GitHub Release assets.

Python 3.10+, standard library only. Never compiles, flashes, or publishes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BOARDS = {"JC4827W543": ("esp32s3", 9), "ST7701_320X820": ("esp32s3", 9),
          "ESP32_C6_LCD_147": ("esp32c6", 13), "CHEAP_YELLOW_DISPLAY": ("esp32", 0),
          "ESP32_S3_AMOLED_143": ("esp32s3", 9)}
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
ROLES = {"bootloader", "partition_table", "ota_data", "application"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular_file(directory, name, limit):
    require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name), "Unsafe filename")
    path = directory / name
    require(not path.is_symlink() and path.is_file() and path.resolve().parent == directory,
            f"Not a regular package file: {name}")
    require(0 < path.stat().st_size <= limit, f"Invalid file size: {name}")
    return path.read_bytes()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_manifest(directory):
    manifest = json.loads(regular_file(directory, "manifest.json", 65536).decode("utf-8-sig"),
                          object_pairs_hook=unique_keys)
    require(isinstance(manifest, dict), "Manifest must be an object")
    return manifest


def validate_package(directory):
    directory = Path(directory).resolve(strict=True)
    m = read_manifest(directory)
    require(m.get("schema_version") == 1 and m.get("package_type") == "esp-image-display-firmware"
            and m.get("installation_type") == "first_install", "Unsupported manifest format")
    board = m.get("board_target")
    require(isinstance(board, str) and board in BOARDS, "Unknown board")
    chip, chip_id = BOARDS[board]
    require(m.get("chip") == chip, "Board/chip mismatch")
    version = m.get("firmware_version")
    require(isinstance(version, str) and VERSION.fullmatch(version), "Invalid version")
    flash = m.get("flash", {})
    require(isinstance(flash, dict), "Invalid flash settings")
    capacity = flash.get("size_bytes")
    require(type(capacity) is int and capacity in [n * 1048576 for n in (1,2,4,8,16,32,64,128)], "Invalid flash size")
    require(flash.get("mode") in ("dio", "dout", "qio", "qout") and
            flash.get("frequency") in ("20m", "26m", "40m", "80m", "120m"), "Invalid flash settings")
    segments = m.get("segments")
    require(isinstance(segments, list) and len(segments) == 4, "Four binary segments are required")
    roles, names, ranges, binaries, clean_segments = {}, set(), [], {}, []
    for segment in segments:
        require(isinstance(segment, dict), "Invalid segment")
        role, name = segment.get("role"), segment.get("file")
        require(isinstance(role, str) and role in ROLES and role not in roles, "Invalid or duplicate segment role")
        require(isinstance(name, str) and name.endswith(".bin") and name.lower() not in names, "Invalid or duplicate binary")
        offset_text = segment.get("offset")
        require(isinstance(offset_text, str) and re.fullmatch(r"0x[0-9a-fA-F]{1,8}", offset_text), "Invalid offset")
        offset, size = int(offset_text, 16), segment.get("size_bytes")
        require(type(size) is int and size > 0 and offset % 4096 == 0 and offset + size <= capacity,
                "Segment exceeds flash or is unaligned")
        data = regular_file(directory, name, capacity)
        digest = hashlib.sha256(data).hexdigest()
        require(len(data) == size and digest == segment.get("sha256"), f"Size/checksum mismatch: {name}")
        if role in ("bootloader", "application"):
            require(len(data) >= 24 and data[0] == 0xE9 and struct.unpack_from("<H", data, 12)[0] == chip_id,
                    f"Incompatible ESP image: {name}")
        names.add(name.lower())
        roles[role] = (offset, data)
        ranges.append((offset, offset + ((size + 4095) // 4096) * 4096))
        binaries[name] = data
        clean_segments.append(dict(role=role, file=name, offset=hex(offset), size_bytes=size, sha256=digest))
    end = 0
    for start, stop in sorted(ranges):
        require(start >= end, "Segments overlap, including erase sectors")
        end = stop
    expected = dict(bootloader=0x1000 if chip == "esp32" else 0,
                    partition_table=0x8000, ota_data=0xE000, application=0x10000)
    require(all(roles[role][0] == offset for role, offset in expected.items()), "Unsupported Arduino layout")
    table, app = roles["partition_table"][1], roles["application"][1]
    require(len(table) <= 4096 and len(roles["ota_data"][1]) <= 8192, "Metadata overlaps reserved settings")
    fits = False
    for index in range(0, len(table) - 31, 32):
        if struct.unpack_from("<H", table, index)[0] != 0x50AA:
            break
        offset, size = struct.unpack_from("<II", table, index + 4)
        if table[index + 2] == 0 and offset == 0x10000 and size >= len(app) and offset + size <= capacity:
            fits = True
    require(fits, "Application does not fit the partition table")
    # Publish only defined metadata; omit arbitrary local paths and extra fields.
    clean = dict(schema_version=1, package_type=m["package_type"], installation_type="first_install",
                 board_target=board, firmware_version=version, identity_source="publisher_declared", chip=chip,
                 flash={key: flash[key] for key in ("mode", "frequency", "size_bytes")},
                 segments=sorted(clean_segments, key=lambda segment: int(segment["offset"], 16)))
    notes = m.get("release_notes", "")
    require(isinstance(notes, str) and len(notes) <= 2000, "Invalid release notes")
    clean["release_notes"] = notes
    if "fqbn" in m:
        board_ids = [chip]
        if board == "ESP32_S3_AMOLED_143" and capacity == 16 * 1048576:
            board_ids.append("waveshare_esp32_s3_touch_amoled_143")
        require(isinstance(m["fqbn"], str) and re.fullmatch(r"esp32:esp32:(?:" + "|".join(board_ids) + r"):[A-Za-z0-9_=,.-]+", m["fqbn"]),
                "Invalid FQBN")
        clean["fqbn"] = m["fqbn"]
    return clean, binaries


def discover(library, version):
    root = Path(library).resolve(strict=True)
    found, visited = [], 0

    def walk(directory, depth):
        nonlocal visited
        visited += 1
        require(visited <= 512, "Library too large")
        if (directory / "manifest.json").exists():
            if read_manifest(directory).get("firmware_version") == version:
                found.append(directory)
        if depth < 2:
            for child in sorted(directory.iterdir()):
                if child.is_dir() and not child.is_symlink():
                    require(child.resolve().is_relative_to(root), "Library path escapes root")
                    walk(child, depth + 1)

    walk(root, 0)
    require(found, f"No packages for version {version}")
    return found


BOARD_LABELS = {
    "JC4827W543": "JC4827W543 (480 x 272)",
    "ST7701_320X820": "Waveshare ST7701 (320 x 820)",
    "ESP32_C6_LCD_147": "ESP32-C6 LCD 1.47 (172 x 320)",
    "CHEAP_YELLOW_DISPLAY": "Cheap Yellow Display (240 x 320)",
    "ESP32_S3_AMOLED_143": "Waveshare ESP32-S3 Touch AMOLED 1.43 (466 x 466)",
}


def public_release_notes(notes, boards, inventory):
    """Keep GitHub descriptions focused on boards, changes, and prepared assets."""
    introduction = ("Firmware packages for all five supported displays." if boards == set(BOARDS)
                    else "Firmware packages for the included displays.")
    introduction += (" Select the package matching your physical board in ESPImageServer’s "
                     "**Set up display** page.")
    included = "\n".join(f"- {label}" for board, label in BOARD_LABELS.items() if board in boards)
    sections = [introduction, "## Included boards\n\n" + included]
    changes = list(re.finditer(
        r"(?m)^ {0,3}##[ \t]+(Changes(?: since [0-9]+\.[0-9]+\.[0-9]+)?)[ \t]*\r?$", notes))
    require(len(changes) == 1, "Release notes must contain exactly one Changes or Changes since <major.minor.patch> section")
    change = changes[0]
    body = re.split(r"(?m)^ {0,3}#{1,6}[ \t]+", notes[change.end():], maxsplit=1)[0].strip()
    sections.append(f"## {change.group(1)}\n\n{body}")
    sections.append("## Prepared assets\n\n" + "".join(inventory).strip())
    return "\n\n".join(sections) + "\n"


def prepare_release(library, version, output_root=ROOT / "dist"):
    require(isinstance(version, str) and VERSION.fullmatch(version), "Invalid release version")
    output_root = Path(output_root).resolve()
    destination = output_root / f"v{version}"
    require(not destination.exists(), f"Output already exists: {destination}. Choose a new --output folder.")
    packages, boards = [], set()
    for directory in discover(library, version):
        manifest, binaries = validate_package(directory)
        board = manifest["board_target"]
        require(board not in boards, f"Duplicate board/version: {board} {version}")
        boards.add(board)
        packages.append((manifest, binaries))
    output_root.mkdir(parents=True, exist_ok=True)
    # Create and clean up only our own staging directory under the output root.
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output_root) as temporary:
        staging = Path(temporary)
        require(staging.resolve().parent == output_root, "Invalid staging location")
        release = staging / f"v{version}"
        release.mkdir()
        sums, inventory = [], []
        for manifest, binaries in sorted(packages, key=lambda package: package[0]["board_target"]):
            name = f"ESPImageDisplay-{manifest['board_target']}-{version}.zip"
            files = {**binaries, "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode(),
                     "LICENSE.txt": (ROOT / "LICENSE").read_bytes()}
            with zipfile.ZipFile(release / name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for filename, data in sorted(files.items()):
                    info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
            checksum = hashlib.sha256((release / name).read_bytes()).hexdigest()
            sums.append(f"{checksum}  {name}\n")
            inventory.append(f"- `{name}` — {manifest['chip']}, {manifest['flash']['size_bytes'] // 1048576} MB flash\n")
        (release / "SHA256SUMS.txt").write_text("".join(sums), encoding="utf-8")
        notes_path = ROOT / "releases" / f"v{version}.md"
        notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        (release / "release-notes.md").write_text(public_release_notes(notes, boards, inventory), encoding="utf-8")
        release.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path, help="Local firmware library (board/version folders)")
    parser.add_argument("--version", required=True, help="Actual compiled version, for example 1.1.5")
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="Output root; existing version folders are never replaced")
    args = parser.parse_args()
    try:
        print(prepare_release(args.library, args.version, args.output))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Release preparation failed: {error}\n")


if __name__ == "__main__":
    main()
