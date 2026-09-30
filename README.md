# ESPImageFirmware

Firmware downloads for displays used with
[ESPImageServer](https://github.com/thelastoutpostworkshop/ESPImageServer).

## Install directly in ESPImageServer

In the updated desktop app, open **Set up display**, connect USB, and choose
**Check display**. The app checks this repository for firmware matching your
board. Select **Review update**, let the app download and verify the package,
then review and confirm installation. No GitHub account, manual download,
extraction, or firmware folder selection is needed.

If the display cannot report its identity yet, choose **Install firmware on
this display**, select the physical model, and download its matching firmware.
Only stable releases with plain major.minor.patch versions are supported.
Drafts and GitHub prereleases are excluded.
The app never flashes a board just because a new release exists.

This requires the desktop app with GitHub firmware support. Older installed
versions can still use the manual steps below until updated.

## Installation and recovery

The desktop app validates the manifest, binary checksums, chip, and
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
