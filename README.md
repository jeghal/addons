# Jeghal Kodi Add-ons

Small download repository for personal Kodi add-ons and skins.

## Available packages

| Add-on | Version | Download | SHA-256 |
| --- | --- | --- | --- |
| Codes IPTV (`plugin.video.my.xtream`) | 3.0.2 | [`plugin.video.my.xtream-3.0.2.zip`](plugin.video.my.xtream-3.0.2.zip) | `48ad7636...` |
| Codes IPTV (permalink) | 3.0.2 | [`plugin.video.my.xtream.zip`](plugin.video.my.xtream.zip) | `48ad7636...` |
| MySkin IPTV v26 Lite (`skin.myskin`) | 4.0.0 | [`MySkin_IPTV_v26_Lite.zip`](MySkin_IPTV_v26_Lite.zip) | `aff1f3e9...` |
| MyCinema (`plugin.video.mycinema`) | 1.0.0 | [`plugin.video.mycinema.zip`](plugin.video.mycinema.zip) | `8d923683...` |
| MyOpenSubtitles (`service.subtitles.myopensubtitles`) | 1.2.0 | [`service.subtitles.myopensubtitles.zip`](service.subtitles.myopensubtitles.zip) | `61f2c804...` |
| vStream Repository (`repository.vstream`) | 0.0.6 | [`repository.vstream-0.0.6.zip`](repository.vstream-0.0.6.zip) | `4339c88c...` |

`plugin.video.my.xtream.zip` always points to the current Codes IPTV package.
Versioned packages remain available for rollback.

## Manual installation

1. Download the required ZIP without extracting it.
2. In Kodi, open **Settings > Add-ons > Install from zip file** and enable *Unknown sources* if required.
3. Select the downloaded ZIP and wait for the installation notification.
4. For Codes IPTV, configure the provider URL, username, and password in the add-on settings.
5. For MyOpenSubtitles, configure your OpenSubtitles.com credentials or SubDL token.
6. For MySkin IPTV, select the skin when Kodi prompts you after installation.

Codes IPTV requires Kodi with Python 3 support (Kodi 19 Matrix or newer). If the provider URL uses plain HTTP,
account credentials are not encrypted in transit. The optional external Arabic translation sends content descriptions
to an unofficial Google Translate endpoint and can be disabled in the settings.

## Integrity verification

SHA-256 hashes for every ZIP are published in [`SHA256SUMS.txt`](SHA256SUMS.txt).

- **Linux / macOS**:
  ```bash
  sha256sum -c SHA256SUMS.txt
  ```

- **Windows PowerShell**:
  ```powershell
  Get-Content SHA256SUMS.txt | ForEach-Object {
      $expected, $file = $_ -split ' +', 2
      $actual = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
      if ($actual -eq $expected) { "$file`: OK" } else { "$file`: MISMATCH" }
  }
  ```

## Current releases

### Codes IPTV 3.0.2 — 2026-10-20

- Current versioned release and permalink target.
- Kodi add-on ID: `plugin.video.my.xtream`.

### MySkin IPTV v26 Lite 4.0.0 — 2026-10-22

- Lightweight IPTV-oriented Kodi skin.
- Kodi add-on ID: `skin.myskin`.

### MyCinema 1.0.0

- Kodi add-on ID: `plugin.video.mycinema`.

### MyOpenSubtitles 1.2.0

- Clean Python 3 package without compiled `__pycache__` bytecode.
