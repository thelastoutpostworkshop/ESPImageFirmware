# ESPImageFirmware

Firmware downloads for displays used with
[ESPImageServer](https://github.com/thelastoutpostworkshop/ESPImageServer).

Download compiled board packages from
[GitHub Releases](https://github.com/thelastoutpostworkshop/ESPImageFirmware/releases).
Each release lists the boards included and their test status. A release may
contain only some of the supported boards.

## Choose your display

| Display | Native size | Target in the download filename |
| --- | --- | --- |
| JC4827W543 | 480 × 272 | `JC4827W543` |
| Waveshare ESP32-S3 3.16-inch / ST7701 | 320 × 820 | `ST7701_320X820` |
| Waveshare ESP32-C6 LCD 1.47 | 172 × 320 | `ESP32_C6_LCD_147` |
| Cheap Yellow Display | 240 × 320 | `CHEAP_YELLOW_DISPLAY` |

Choose the exact display model. The two ESP32-S3 displays use different
firmware even though they share a chip family.

## Install directly in ESPImageServer

In the updated desktop app, open **Set up display**, connect USB, and choose
**Check display**. The app checks this repository for firmware matching your
board. Select **Review update**, let the app download and verify the package,
then review and confirm installation. No GitHub account, manual download,
extraction, or firmware folder selection is needed.

If the display cannot report its identity yet, choose **Install firmware on
this display**, select the physical model, and download its matching firmware.
**Include preview firmware releases** makes preview builds available explicitly.
The app never flashes a board just because a new release exists.

This requires the desktop app with GitHub firmware support. Older installed
versions can still use the manual steps below until updated.

## Manual installation / older desktop apps

1. Download the board's ZIP from a release's **Assets** list. For example:
   `ESPImageDisplay-CHEAP_YELLOW_DISPLAY-1.1.5.zip`.
2. Extract it into your local firmware library. Keep each board/version in its
   own folder, with `manifest.json` directly inside the version folder:

   ```text
   ESPImage Firmwares/
     CheapYellowDisplay/
       1.1.5/
         manifest.json
         ESPImageDisplay.ino.bin
         ESPImageDisplay.ino.bootloader.bin
         ESPImageDisplay.ino.partitions.bin
         boot_app0.bin
         LICENSE.txt
   ```

3. Connect the display using its data USB connector and a data-capable cable.
4. In ESPImageServer, open **Set up display**, select the USB port, and check
   the display. Choose the firmware library and check for updates, or select
   the extracted version folder through **Install a different package**.
5. Review the board, version, and installation notice. Keep USB connected
   through writing, verification, and restart.
6. Set up Wi-Fi if requested. Confirm the display reaches **Ready**.

Manual downloads remain available for offline use and older desktop apps.
GitHub's automatically generated **Source code** archives contain this
repository's documentation and tools, not compiled firmware.

## Installation and recovery

These are complete **first-install packages**, not guaranteed settings-preserving
updates. The desktop app validates the manifest, binary checksums, chip, and
partition layout. An installation may lose settings if the previous partition
layout differs. Full-chip erase is not used by default.

A verified write and a successful application boot are separate checks. If the
write is interrupted, follow the desktop app's BOOT/RESET recovery instructions
for the board and reinstall the complete package. Close serial monitors if the
USB port is busy. Use the board's documented data connector and reset procedure;
connector layouts differ between models.

`SHA256SUMS.txt` accompanies each prepared release. To compare a downloaded ZIP:

```powershell
Get-FileHash -Algorithm SHA256 .\ESPImageDisplay-CHEAP_YELLOW_DISPLAY-1.1.5.zip
```

## Source and maintainers

Firmware source is maintained in the
[ESPImageDisplay project](https://github.com/thelastoutpostworkshop/JC4827W543_ai).
This repository contains distribution tools, instructions, and release notes.
Firmware incorporates third-party components that retain their own licenses;
the project's MIT notice is included with each prepared package.

See [RELEASING.md](RELEASING.md) to prepare release assets. Firmware is compiled
manually, and the packaging tool never flashes a board or publishes a release.
