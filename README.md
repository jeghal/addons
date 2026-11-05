# Jeghal Kodi Add-ons

Small download repository for personal Kodi add-ons and skins.

## Available packages

| Add-on | Version | Download | SHA-256 |
| --- | --- | --- | --- |
| Codes IPTV (`plugin.video.my.xtream`) | 3.0.3 | [`plugin.video.my.xtream-3.0.3.zip`](plugin.video.my.xtream-3.0.3.zip) | `13a6649a...` |
| Codes IPTV (permalink) | 3.0.3 | [`plugin.video.my.xtream.zip`](plugin.video.my.xtream.zip) | `13a6649a...` |
| MySkin IPTV v26 Lite (`skin.myskin`) | 4.0.0 | [`MySkin_IPTV_v26_Lite.zip`](MySkin_IPTV_v26_Lite.zip) | `e2c86230...` |
| MyCinema (`plugin.video.mycinema`) | 1.0.0 | [`plugin.video.mycinema.zip`](plugin.video.mycinema.zip) | `8d923683...` |
| MyOpenSubtitles (`service.subtitles.myopensubtitles`) | 1.2.0 | [`service.subtitles.myopensubtitles.zip`](service.subtitles.myopensubtitles.zip) | `c54e9ba4...` |
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

### Codes IPTV 3.0.3 — 2026-11-05

- Ma sélection: public TMDb list with movies and series, loaded on demand.
- French interface and stock Kodi icons for the main menu.
- Improved IPTV matching for provider tags and localized subtitles (Ghosts 2021).
- Original and French title matching, with cached TMDb names and deduplicated results.
- Full-catalog warmup no longer starts automatically; search and manual refresh remain available.
- Automated checks: 87 passed, 8 legacy comparisons skipped, no failures. User tested in Kodi.
- Current versioned release and permalink target.

### Codes IPTV 3.0.2 — 2026-10-20

- Previous version retained for rollback.
- Kodi add-on ID: `plugin.video.my.xtream`.

### MySkin IPTV v26 Lite 4.0.0 — revised 2026-11-05

- Lightweight IPTV-oriented Kodi skin.
- Two-column TV group grid with French names, category-count badges and static cyan focus.
- Matching static cards for search and Guide cinéma (Explorer TMDb / Ma sélection); data loads only on click. Clicking Rechercher opens global IPTV search; Right opens the search cards.
- Fixed opaque focus overlay: shared library/browser focus now uses four thin cyan edges.
- Local history progress, empty states, per-widget position memory, cyan library focus and direct Guide cinéma access.
- French home labels, short shortcuts, larger history posters, fixed cyan focus and separate confirmed history-clear button. Categories sit below the clock; sidebar geometry unchanged. Same package name and version.
- Kodi add-on ID: `skin.myskin`.

### MyCinema 1.0.0

- Kodi add-on ID: `plugin.video.mycinema`.

### MyOpenSubtitles 1.2.0 — revised 2026-11-05

- Expired OpenSubtitles sessions renew once on HTTP 401, with a bounded retry.
- SubDL season packs select the requested episode; ambiguous files require a manual choice.
- Provider language tags and duplicate release years are removed from subtitle search titles.
- SubDL unmatched-title responses are treated as empty results, not service failures.
- Each distinct OpenSubtitles file is selectable; provider errors preserve other results.
- Kodi requests always finish, including failed downloads and cancelled selection.
- Automated tests: 42 passed. Two live search checks succeeded; download/login renewal tested offline.
- Same version and package names; clean Python 3 ZIP without compiled bytecode.
