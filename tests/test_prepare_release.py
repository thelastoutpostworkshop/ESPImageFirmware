import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location(
    "prepare_release", Path(__file__).resolve().parents[1] / "scripts" / "prepare_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="espimage-release-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.library = self.root / "library"
        self.package = self.library / "CheapYellowDisplay" / "1.1.5"
        self.package.mkdir(parents=True)
        image = bytearray(256)
        image[0] = 0xE9
        table = struct.pack("<HBBII16sI", 0x50AA, 0, 0, 0x10000, 0x100000, b"factory", 0)
        binaries = {"bootloader": (0x1000, image), "partition_table": (0x8000, table),
                    "ota_data": (0xE000, bytes(8192)), "application": (0x10000, image)}
        self.manifest = dict(schema_version=1, package_type="esp-image-display-firmware",
            installation_type="first_install", board_target="CHEAP_YELLOW_DISPLAY",
            chip="esp32", firmware_version="1.1.5",
            flash=dict(mode="dio", frequency="80m", size_bytes=4194304), segments=[])
        for role, (offset, data) in binaries.items():
            name = role + ".bin"
            (self.package / name).write_bytes(data)
            self.manifest["segments"].append(dict(role=role, file=name, offset=hex(offset),
                size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        self.save()

    def save(self):
        (self.package / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def replace_binary(self, role, data):
        segment = next(s for s in self.manifest["segments"] if s["role"] == role)
        (self.package / segment["file"]).write_bytes(data)
        segment.update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.save()

    def test_version_suffixes_rejected(self):
        for version in ('1.2.0-beta', '1.2.0+build'):
            with self.subTest(version=version):
                with self.assertRaisesRegex(ValueError, 'version'):
                    release.prepare_release(self.library, version, self.root / 'out')
                self.manifest['firmware_version'] = version
                self.save()
                with self.assertRaisesRegex(ValueError, 'version'):
                    release.validate_package(self.package)

    def test_amoled_release_uses_s3_headers_and_board_filename(self):
        self.manifest.update(board_target="ESP32_S3_AMOLED_143", chip="esp32s3")
        self.manifest["fqbn"] = "esp32:esp32:waveshare_esp32_s3_touch_amoled_143:FlashMode=qio,PSRAM=enabled"
        self.manifest["flash"]["size_bytes"] = 16 * 1048576
        for role in ("application", "bootloader"):
            segment = next(s for s in self.manifest["segments"] if s["role"] == role)
            image = bytearray((self.package / segment["file"]).read_bytes())
            image[12:14] = (9).to_bytes(2, "little")
            if role == "bootloader":
                segment["offset"] = "0x0"
            self.replace_binary(role, image)
        output = release.prepare_release(self.library, "1.1.5", self.root / "out")
        self.assertTrue((output / "ESPImageDisplay-ESP32_S3_AMOLED_143-1.1.5.zip").is_file())
        self.manifest["board_target"] = "ST7701_320X820"
        self.save()
        with self.assertRaisesRegex(ValueError, "Invalid FQBN"):
            release.validate_package(self.package)

    def test_release_contains_only_installation_files_and_valid_checksum(self):
        (self.package / "secrets.h").write_text("private fixture")
        self.manifest["local_build_path"] = "private fixture path"
        self.save()
        output = release.prepare_release(self.library, "1.1.5", self.root / "out")
        archive_path = next(output.glob("*.zip"))
        with zipfile.ZipFile(archive_path) as archive:
            self.assertEqual(set(archive.namelist()),
                {s["file"] for s in self.manifest["segments"]} | {"manifest.json", "LICENSE.txt"})
            self.assertNotIn("local_build_path", json.loads(archive.read("manifest.json")))
            extracted = self.root / "extracted"
            archive.extractall(extracted)
        validated, _ = release.validate_package(extracted)
        self.assertEqual(validated["board_target"], "CHEAP_YELLOW_DISPLAY")
        self.assertEqual((output / "SHA256SUMS.txt").read_text().strip(),
            hashlib.sha256(archive_path.read_bytes()).hexdigest() + "  " + archive_path.name)

    def test_public_notes_keep_only_requested_sections_and_actual_assets(self):
        source = self.root / "release-source"
        (source / "releases").mkdir(parents=True)
        (source / "LICENSE").write_bytes((release.ROOT / "LICENSE").read_bytes())
        notes = ("# ESPImageDisplay 1.1.5\n\nInternal preparation status.\n\n"
                 "## Release readiness\n\nNot recorded.\n\n"
                 "## Included boards\n\n- Stale board\n\n"
                 "## Changes since 1.1.4\n\n- Better saves.\n\n"
                 "  ### Internal validation\n\nPrivate review details.\n\n"
                 "## App compatibility\n\nInternal compatibility details.\n\n"
                 "## Validation and provenance\n\nInternal build details.\n\n"
                 "## Notices\n\nRetained in the package.\n\n"
                 "## Prepared assets\n\n- old.zip\n")
        notes_path = source / "releases" / "v1.1.5.md"
        notes_path.write_text(notes, encoding="utf-8")
        with patch.object(release, "ROOT", source):
            output = release.prepare_release(self.library, "1.1.5", self.root / "out")
        expected = ("Firmware packages for the included displays. Select the package matching your physical board "
                    "in ESPImageServer’s **Set up display** page.\n\n"
                    "## Included boards\n\n- Cheap Yellow Display (240 x 320)\n\n"
                    "## Changes since 1.1.4\n\n- Better saves.\n\n"
                    "## Prepared assets\n\n"
                    "- `ESPImageDisplay-CHEAP_YELLOW_DISPLAY-1.1.5.zip` — esp32, 4 MB flash\n")
        self.assertEqual((output / "release-notes.md").read_text(encoding="utf-8"), expected)
        self.assertEqual(notes_path.read_text(encoding="utf-8"), notes)

    def test_public_notes_list_all_five_displays_in_requested_order(self):
        notes = release.public_release_notes("## Changes since 1.1.39\n\n- Better saves.\n",
                                             set(release.BOARDS), ["- prepared.zip\n"])
        self.assertTrue(notes.startswith("Firmware packages for all five supported displays."))
        self.assertIn("## Included boards\n\n"
                      "- JC4827W543 (480 x 272)\n"
                      "- Waveshare ST7701 (320 x 820)\n"
                      "- ESP32-C6 LCD 1.47 (172 x 320)\n"
                      "- Cheap Yellow Display (240 x 320)\n"
                      "- Waveshare ESP32-S3 Touch AMOLED 1.43 (466 x 466)\n\n", notes)
        self.assertEqual([line for line in notes.splitlines() if line.startswith("#")],
                         ["## Included boards", "## Changes since 1.1.39", "## Prepared assets"])

    def test_missing_or_ambiguous_changes_do_not_create_a_release(self):
        source = self.root / "release-source"
        (source / "releases").mkdir(parents=True)
        (source / "LICENSE").write_bytes((release.ROOT / "LICENSE").read_bytes())
        for notes in ("", "## Changes\n- First.\n## Changes since 1.1.4\n- Second.\n"):
            with self.subTest(notes=notes), patch.object(release, "ROOT", source):
                (source / "releases" / "v1.1.5.md").write_text(notes, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "exactly one Changes"):
                    release.prepare_release(self.library, "1.1.5", self.root / "out")
                self.assertFalse((self.root / "out" / "v1.1.5").exists())

    def test_tampering_rejected_without_partial_release(self):
        (self.package / "application.bin").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "checksum"):
            release.prepare_release(self.library, "1.1.5", self.root / "out")
        self.assertFalse((self.root / "out" / "v1.1.5").exists())

    def test_wrong_chip_rejected_even_with_matching_checksum(self):
        data = bytearray((self.package / "application.bin").read_bytes())
        struct.pack_into("<H", data, 12, 9)
        self.replace_binary("application", data)
        with self.assertRaisesRegex(ValueError, "Incompatible ESP"):
            release.validate_package(self.package)

    def test_application_partition_too_small_rejected(self):
        data = bytearray((self.package / "partition_table.bin").read_bytes())
        struct.pack_into("<I", data, 8, 128)
        self.replace_binary("partition_table", data)
        with self.assertRaisesRegex(ValueError, "partition table"):
            release.validate_package(self.package)

    def test_path_escape_rejected(self):
        self.manifest["segments"][0]["file"] = "../bootloader.bin"
        self.save()
        with self.assertRaisesRegex(ValueError, "Unsafe filename"):
            release.validate_package(self.package)

    def test_duplicate_board_rejected(self):
        duplicate = self.library / "duplicate"
        duplicate.mkdir()
        for source in self.package.iterdir():
            (duplicate / source.name).write_bytes(source.read_bytes())
        with self.assertRaisesRegex(ValueError, "Duplicate board"):
            release.prepare_release(self.library, "1.1.5", self.root / "out")

    def test_existing_release_preserved(self):
        output = release.prepare_release(self.library, "1.1.5", self.root / "out")
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        with self.assertRaisesRegex(ValueError, "already exists"):
            release.prepare_release(self.library, "1.1.5", self.root / "out")
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_zip_is_reproducible(self):
        first = release.prepare_release(self.library, "1.1.5", self.root / "first")
        second = release.prepare_release(self.library, "1.1.5", self.root / "second")
        self.assertEqual(next(first.glob("*.zip")).read_bytes(), next(second.glob("*.zip")).read_bytes())


if __name__ == "__main__":
    unittest.main()
