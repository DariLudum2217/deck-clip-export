# Deck Clip Export

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin that exports Steam Game Recording clips to standard MP4 files and sends recordings and screenshots to other devices with [LocalSend](https://localsend.org) or [Syncthing](https://syncthing.net). All setup is done in Game Mode, without Desktop Mode or a terminal.

In Game Mode, Steam can only share a trimmed piece of a recording, shorter than a minute; a full recording can be saved as a video file only in Desktop Mode. On disk, recordings are stored as DASH segments rather than video files. This plugin exports full recordings from Game Mode.

[Русская версия](README.ru.md)

## Features

- **MP4 export.** The segments of a recording are joined into a standard `.mp4` without re-encoding, so export is fast and lossless. HEVC video is tagged for compatibility with Apple devices.
- **Browser for screenshots and recordings.** Grouped by day or shown as a single grid, with adjustable tile size and filters by type and game; controller-friendly selection for batch actions.
- **Two ways of sending.** Choose the method that suits you, or use both:
  - **LocalSend** sends selected files directly to a smartphone, tablet or computer on the same network. Receiving devices are found automatically or can be added by address.
  - **Syncthing** (optional) keeps a folder synchronised with your other devices over the local network or the internet. Sent files arrive automatically, without confirmation.

  No cloud storage, accounts or file size limits are involved.
- **Storage management.** The plugin's own copies (exported MP4 files and outgoing Syncthing copies) can be removed manually or automatically after sending. Original Steam screenshots and recordings are never modified or deleted.
- **English and Russian** interface, selected according to the Steam client language.

## Installation

1. Download `deck-clip-export.zip` from the [latest release](../../releases/latest).
2. In Decky, open Settings → General and enable **Developer mode**.
3. Open Settings → Developer → **Install Plugin from ZIP** and select the downloaded file.

## Initial setup

Open the Quick Access menu → Decky → Deck Clip Export → **Setup**.

1. **ffmpeg.** Select Install if ffmpeg is not found (approx. 30 MB). If the system already provides ffmpeg, no action is required.
2. **LocalSend.** Install [LocalSend](https://localsend.org) on the device that will receive files. The app is free and available for Android, iPhone and iPad, Windows, macOS and Linux. Open it, make sure both devices are connected to the same network, then select **Search** in Setup.
3. **Syncthing (optional).** Select **Turn on** in the Syncthing card, then **Install** if Syncthing is not found (approx. 12 MB). If Syncthing is already installed, the plugin uses the existing installation. Install Syncthing on the receiving device (Syncthing-Fork for Android, Möbius Sync for iPhone and iPad, or Syncthing for a computer), add a new device in the app and scan the QR code shown in Setup. When the connection request appears, select **Approve**, then accept the "Deck Clip Export" folder on the receiving device.

With LocalSend, each transfer has to be accepted on the receiving device by default. To receive files without confirmation, enable **Quick Save** in LocalSend.

With Syncthing, keep the default folder type on the receiving device, **Send & Receive**. On a smartphone, it is recommended to place the folder in `DCIM` so that received files appear in the photo gallery. The **Receive Only** type is not recommended: with it, removed copies are reported as local changes, and the **Revert Local Changes** button deletes those files from the receiving device.

## Sending files

Press Y on a tile, select **Send** in the item view, or select several items with X and press Y or choose **Send** in the top bar. The dialog offers:

- **Syncthing**, the synced folder (when Syncthing is turned on and set up);
- **LocalSend**, the devices found on the network, with the most recently used device first.

Recordings are exported to MP4 automatically before sending. The progress of a transfer is shown on the tiles, and a notification appears when it completes or fails.

If a LocalSend device requires a PIN, enter it in the dialog before selecting the device. If a device is not found automatically, enter its address (shown in LocalSend on the Receive tab) and select **Connect**.

### Smartphone hotspot

On some smartphones, automatic discovery does not work while they act as a hotspot. If the handheld is connected to a smartphone's hotspot and the smartphone is not found, enter the smartphone's address manually. It is usually the gateway address, which is shown in Setup.

## Controls

| Button | Action |
| --- | --- |
| A | Open the item view (preview, export, send, remove copies) |
| X | Select or deselect for batch actions |
| Y | Send (the selection, if there is one) |
| Menu (≡) | Remove copies |

The first row of the top bar contains the filters, the view mode switch (by day or grid) and tile size controls (− / +). The second row contains selection actions and **Remove all copies**.

## Storage management

The plugin creates its own files: the exported MP4 of a recording and, when sending via Syncthing, an outgoing copy in the synced folder. The outgoing copy is a hardlink, so it does not take additional space while the MP4 file exists; a screenshot's outgoing copy is a hardlink to the Steam file. **Remove copies** deletes these files. Steam screenshots and recordings are always kept, and the copies can be created again at any time. Files already sent are stored on the receiving devices independently and are not affected.

By default, Syncthing propagates deletions to all connected devices. To prevent this, the plugin first adds the outgoing copy to the Syncthing ignore list on the handheld (lines marked "Deck Clip Export" in the folder's `.stignore` file), waits for Syncthing to confirm the change and only then deletes the file. Do not remove these lines from `.stignore`. If Syncthing is not running, removal is cancelled. A file sent again later receives a numbered name, for example `…_2.mp4`, because the previous name remains excluded from sync.

**Remove copies after sending** (Quick Access menu, disabled by default):

- LocalSend: the MP4 file is deleted as soon as it has been sent;
- Syncthing: every 20 seconds the plugin checks which sent files another device has received in full and removes their copies.

## Settings

The following options are available in the Quick Access menu:

- Sending via Syncthing, outgoing folder (default: `~/Sync/Deck Clip Export`) and sorting into per-game folders
- Automatic removal of copies after sending
- Gallery view mode and tile size
- MP4 export folder (default: `~/Videos/Steam Recordings`)
- Additional recording folders, if Steam records to another drive

## Compatibility

The plugin is intended for any x86_64 system that runs Decky Loader in Steam Game Mode, including Steam Deck (SteamOS), Bazzite and ChimeraOS. It has been developed and tested on a GPD Win Mini running Bazzite. Flatpak installations of Steam are also supported.

The plugin implements the sending side of LocalSend protocol version 2, including the client certificate required by LocalSend 1.18 and later, and works with the official LocalSend apps. It does not receive files.

## File locations

| Contents | Location |
| --- | --- |
| Plugin settings, saved LocalSend devices, configuration of the bundled Syncthing | `~/homebrew/settings/deck-clip-export/` |
| Downloaded ffmpeg and Syncthing, thumbnail cache | `~/homebrew/data/deck-clip-export/` |
| Logs | `~/homebrew/logs/deck-clip-export/` |
| Web interface of the Syncthing instance installed by the plugin | `http://127.0.0.1:8384` (or the next available port) |

The Syncthing instance installed by the plugin runs while Decky is running and sending via Syncthing is turned on. Turning it off stops that instance; uninstalling the plugin stops it and removes the downloaded programs.

## Troubleshooting

- **The gallery does not load or shows an error.** Check the log files in the folder listed above.
- **The LocalSend device is not found.** Make sure LocalSend is open on it and both devices are on the same network. Some routers isolate wireless clients from each other (guest networks, "AP isolation"); in that case devices cannot reach each other. Try entering the address manually.
- **The LocalSend transfer does not start.** Check whether the receiving device is waiting for the transfer to be accepted. If no response is given within five minutes, the request is cancelled.
- **"Syncthing is installed but not running"** with a separately installed Syncthing. Start it, for example with `systemctl --user enable --now syncthing`.
- **Steam does not finish loading after Decky is restarted.** Avoid restarting Decky (`systemctl restart plugin_loader`) while Steam is running in Desktop Mode. Restart Decky from Game Mode or with Steam closed.

## Building from source

```
pnpm install
pnpm run build
```

Copy `dist/`, `main.py`, `plugin.json`, `package.json` and `LICENSE` to `~/homebrew/plugins/deck-clip-export/` and restart Decky. Publishing a GitHub release triggers a GitHub Actions workflow that builds the installable archive and attaches it to the release.

The backend (`main.py`) intentionally relies only on basic Python modules, because the Python runtime bundled with Decky does not include the full standard library. Network requests to LocalSend devices are made with `curl`, and the LocalSend client certificate is created with `openssl`.

## Third-party software

The following programs are not bundled with the plugin. They are downloaded on request from their official GitHub releases and verified against a pinned SHA-256 checksum.

- [Syncthing](https://github.com/syncthing/syncthing) v2.1.6, MPL-2.0
- [ffmpeg](https://ffmpeg.org) 7.0.2, static build by John Van Sickle, distributed by [ffmpeg-static](https://github.com/eugeneware/ffmpeg-static), GPL-3.0

This plugin is not affiliated with the LocalSend or Syncthing projects.

## License

BSD-3-Clause. See [LICENSE](LICENSE).

Author: Dari Ludum ([@DariLudum2217](https://github.com/DariLudum2217)).
