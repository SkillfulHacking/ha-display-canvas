# Display Canvas

Display Canvas is a Home Assistant custom integration for managing image libraries and publishing them to display devices and screensavers.

It provides Home Assistant-native image feeds for:

- Projectivy Launcher via Overflight
- Aerial Views
- Home Assistant media sources
- Camera-backed images
- AI-generated artwork
- Uploaded images
- Local media folders

## Features

- Named reusable image libraries
- Home Assistant Media Browser integration
- Camera-backed libraries
- Per-feed library selection
- Landscape and portrait filtering
- Minimum resolution filtering
- Feed image counts
- Stable image URLs with cache busting
- Overflight JSON feed
- Aerial Views CSV feed
- Local-first operation
- No external cloud service required

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Open **Integrations**.
3. Add this repository as a custom repository:
   `https://github.com/SkillfulHacking/ha-display-canvas`
4. Select category **Integration**.
5. Install **Display Canvas**.
6. Restart Home Assistant.

### Manual

Copy:

```text
custom_components/display_canvas
```

into:

```text
/config/custom_components/display_canvas
```

Then restart Home Assistant.

## Setup

After restarting:

1. Go to **Settings → Devices & services**.
2. Select **Add Integration**.
3. Search for **Display Canvas**.
4. Add the integration.

Only one Display Canvas configuration entry is required.

## Libraries

Libraries are reusable named image sources.

Examples:

- AI Art
- Uploaded Images
- Fantasy Ambient Art
- Local History
- Frigate People Today

A library may use:

- a browsable Home Assistant media folder
- an image media source
- a Home Assistant camera entity

Libraries are managed from:

**Settings → Devices & services → Display Canvas → Configure → Libraries**

## Display Feeds

Display Canvas currently provides two feed formats.

### Projectivy / Overflight

The Overflight endpoint publishes JSON suitable for Projectivy Launcher.

Configure it under:

**Display Canvas → Configure → Projectivy / Overflight**

You can select:

- Library
- Orientation
- Minimum resolution

Copy the generated URL from:

**Display Canvas → Configure → Feed URLs**

Then use that URL as the Overflight feed in Projectivy.

### Aerial Views

The Aerial endpoint publishes a CSV playlist suitable for Aerial Views.

Configure it under:

**Display Canvas → Configure → Aerial Views**

You can select:

- Library
- Orientation
- Minimum resolution

Copy the generated URL from:

**Display Canvas → Configure → Feed URLs**

Use that URL as the custom remote playlist in Aerial Views.

## Image Filtering

Each feed can independently filter images by orientation:

- Any
- Landscape
- Portrait

Minimum resolution options:

- Any
- 720p
- 1080p
- 1440p
- 4K

Resolution filtering uses the image's long and short edges and does not require a 16:9 aspect ratio.

EXIF image rotation is respected when determining orientation.

## Base URL

Display Canvas normally uses Home Assistant's local URL when generating image links.

A custom Base URL may be configured under:

**Display Canvas → Configure → General**

This is useful when display devices must access Home Assistant through a specific hostname, IP address, or reverse proxy.

## Security

Display Canvas feed URLs contain an access token.

Treat feed URLs like credentials:

- Do not publish them publicly.
- Do not include them in screenshots or bug reports.
- Regenerate the token if it is exposed.

The token allows access only to Display Canvas feeds and published media, not general Home Assistant API access.

## Automation

Display Canvas provides Home Assistant actions for managing feed sources and libraries:

- `display_canvas.set_source`
- `display_canvas.save_library`
- `display_canvas.remove_library`
- `display_canvas.set_library`

Library selection is also exposed through Home Assistant select entities for Overflight and Aerial Views.

## Development

Validation runs automatically on pull requests using:

- HACS validation
- Home Assistant Hassfest
- pytest regression tests

Current regression coverage includes:

- orientation filtering
- resolution thresholds
- square image handling
- EXIF rotation
- feed URL generation
- Home Assistant local URL fallback

## Supported Home Assistant Version

Display Canvas is currently developed and tested against Home Assistant 2026.10.

## Status

Display Canvas is pre-1.0 software.

Configuration and feed formats are intended to remain stable, but breaking changes may still occur before the first stable release.

## License

See [LICENSE](LICENSE).
