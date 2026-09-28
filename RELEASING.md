# Preparing a firmware release

## Local inputs

Compile the desired board manually in ESPImageDisplay. Confirm its target and
version before compilation. Create its local `manifest.json` using
ESPImageServer's `scripts/package-firmware.ps1` as usual. Use a fresh build
with Wi-Fi credentials supplied through USB/device storage.

The local library can include older versions and build metadata. The release
preparer scans only the library root, board folders, and version folders. It
selects the exact requested version and rejects duplicate board/version pairs.

## Prepare the assets

Python 3.10 or newer is required for maintainers. No additional Python packages
are needed. Run from this repository:

```powershell
python -m unittest discover -s tests -v
python scripts/prepare_release.py --library 'C:\Users\charles\Desktop\ESPImage Firmwares' --version 1.1.4
python scripts/prepare_release.py --library 'C:\Users\charles\Desktop\ESPImage Firmwares' --version 1.1.5
```

For each selected package the script checks the manifest format, board/chip,
file sizes and SHA-256 hashes, ESP image chip headers, flash capacity, offsets,
erase-sector overlap, and application partition fit. Board identity/version
are publisher declarations, to be checked against the actual build and after
flashing; binary validation alone does not establish hardware acceptance or
the absence of compiled credentials.

Output goes to `dist/v<version>/`:

- One `ESPImageDisplay-<BOARD_TARGET>-<version>.zip` per included board.
- `SHA256SUMS.txt` for those ZIPs.
- `release-notes.md`, based on the matching file in `releases/`, with an asset list.

ZIPs contain only a cleaned manifest, its four binaries, and the project license.
They exclude `build.options.json`, `flash_args`, source, logs, ELF/map files,
merged binaries, and unrelated files. ZIP timestamps are fixed for repeatable
output. The original local packages are never edited.

Existing output folders are never replaced. To prepare a fresh comparison,
pass `--output` with another output root. Do not replace already published
firmware with different bytes under the same version; assign a new version.

## Review and publish

1. Record the included boards, source/build provenance, changes, hardware
   results, and remaining limitations in `releases/v<version>.md`. Only claim
   tests actually performed. Retain applicable dependency license notices
   with the release materials.
2. Prepare the assets, extract each ZIP, and check that ESPImageServer accepts
   it. Complete the intended physical-board checks. A successful packaging
   test does not prove flashing, boot, Wi-Fi, or recovery.
3. Commit and push the documentation, scripts, tests, and reviewed release notes.
   Generated binaries and ZIPs remain outside Git history (`dist/` is ignored).
4. On the repository's **Releases** page, choose **Draft a new release** and
   create the matching `v<version>` tag. This tag identifies the distribution
   repository revision; it is not automatically the firmware source commit.
5. Paste the generated `dist/v<version>/release-notes.md` into the description.
   Attach the ZIPs and `SHA256SUMS.txt`. Save the draft for review. Keep it unpublished when hardware acceptance
   remains incomplete; do not publish prereleases.
6. Publish when the listed test status and assets are ready for users.

GitHub documents the draft, asset-upload, and publication steps in
[Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).
The local preparation command does not create commits, tags, drafts, or uploads.

## Current preparation

- **1.1.39:** All five boards; explicit board identity in network registration. Maintainer-confirmed credential-free builds and hardware readiness. See `releases/v1.1.39.md` and `releases/v1.1.39-builds.json`.

- **1.1.38:** All five supported boards; maintainer-confirmed credential-free release builds. See `releases/v1.1.38.md` and `releases/v1.1.38-builds.json`.

- **1.1.13:** Waveshare ESP32-S3 Touch AMOLED 1.43; maintainer-confirmed release build. See `releases/v1.1.13.md` for provenance and validation.

- **1.1.4:** JC4827W543, ESP32-C6 LCD 1.47, and Waveshare ST7701 320×820.
- **1.1.5:** Cheap Yellow Display; the new status layout is included. Its
  physical hardware acceptance has not yet been recorded here.

Do not advertise 1.1.5 packages for other boards until they have been compiled,
packaged, and checked. See each version's release notes for the current evidence.

## Upload and publish from this checkout

The desktop app discovers published releases in this repository by exact board
filename, version tag, and accompanying `SHA256SUMS.txt`. It downloads and
validates ZIPs automatically. Keep this naming format for future releases.
Drafts and GitHub prereleases are excluded from the app. Only plain
major.minor.patch versions are accepted, with no version suffixes. A release may include only the boards compiled for that version.

After reviewing the notes and pushing this repository's changes, upload with:

```powershell
python scripts/publish_release.py --version 1.1.4 --publish
python scripts/publish_release.py --version 1.1.5 --publish
```

Omit `--publish` to leave a draft. The uploader uses your configured Git
credential helper, verifies uploaded hashes, and refuses to replace published
assets. It can resume an incomplete draft if existing asset hashes match.
It does not compile firmware or publish an ESPImageServer installer.


## AMOLED target preparation

`ESP32_S3_AMOLED_143` is accepted by the preparation tool as ESP32-S3.
Use ESPImageServer's updated package-firmware.ps1 for the named Arduino board
`waveshare_esp32_s3_touch_amoled_143`, whose flash size is fixed at 16 MB.
The asset must be `ESPImageDisplay-ESP32_S3_AMOLED_143-<version>.zip`.
AMOLED firmware is packaged in version 1.1.13. For later releases, compile,
package, and record physical acceptance before publishing.
