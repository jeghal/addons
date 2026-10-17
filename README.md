# Jeghal Kodi Add-ons

Small download repository for personal Kodi add-ons.

## Available packages

| Add-on | Version | Download | SHA-256 |
| --- | --- | --- | --- |
| Codes IPTV (`plugin.video.my.xtream`) | 3.0.0 | [`plugin.video.my.xtream-3.0.0.zip`](plugin.video.my.xtream-3.0.0.zip) | `b07a23c7...` |
| Codes IPTV (Permalink) | 3.0.0 | [`plugin.video.my.xtream.zip`](plugin.video.my.xtream.zip) | `b07a23c7...` |
| vStream Repository (`repository.vstream`) | 0.0.6 | [`repository.vstream-0.0.6.zip`](repository.vstream-0.0.6.zip) | `4339c88c...` |
| MyOpenSubtitles (`service.subtitles.myopensubtitles`) | 1.2.0 | [`service.subtitles.myopensubtitles.zip`](service.subtitles.myopensubtitles.zip) | `dbc96732...` |

`plugin.video.my.xtream.zip` always points to the current Codes IPTV package.

## Manual installation

1. Download the required ZIP without extracting it.
2. In Kodi, open **Settings > Add-ons > Install from zip file** (ensure *Unknown sources* is enabled).
3. Select the downloaded ZIP and wait for the installation notification.
4. For Codes IPTV: configure provider URL, username, and password in the add-on settings.
5. For MyOpenSubtitles: configure your OpenSubtitles.com credentials or SubDL token in the subtitle settings.

Codes IPTV requires Kodi with Python 3 support (Kodi 19 Matrix, 20 Nexus, 21 Omega). If the provider URL uses plain
HTTP, account credentials are not encrypted in transit. The optional external
Arabic translation sends content descriptions to an unofficial Google
Translate endpoint and can be disabled in the settings.

## Integrity verification

SHA-256 hashes are published in [`SHA256SUMS.txt`](SHA256SUMS.txt).

- **Linux / macOS**:
  ```bash
  sha256sum -c SHA256SUMS.txt
  ```

- **Windows PowerShell**:
  ```powershell
  Get-FileHash plugin.video.my.xtream-3.0.0.zip
  ```
  Or verify all files at once:
  ```powershell
  Get-Content SHA256SUMS.txt | ForEach-Object { $h,$f = $_ -split ' +'; if ((Get-FileHash $f).Hash.ToLower() -eq $h) { "${f}: OK" } else { "${f}: MISMATCH" } }
  ```

## Release notes

### Codes IPTV 3.0.0 — 2026-10-17

- Modular Python 3 architecture (`core`, `api`, `domain`, `storage`, `services`, `ui`, `playback`, `views`).
- Safer playback URLs, atomic cache/history writes and crash-recoverable locks.
- Account-isolated history and bounded episode resume points.
- Background catalog pre-cache and lazy route loading.
- TMDb cinema guide, artwork cache and safer provider-image handling.
- Optimized UI icons (package size reduced to ~2.05 MiB).

### MyOpenSubtitles 1.2.0 — Cleaned package

- Removed compiled `__pycache__` bytecode for universal Python 3 compatibility.


