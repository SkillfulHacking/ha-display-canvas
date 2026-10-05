# Display Canvas

Manage, generate, curate, and publish visual media across your Home Assistant displays.

## Goals

Display Canvas provides a Home Assistant-native visual media layer for:

- Projectivy Launcher via Overflight
- Aerial Views
- Home Assistant dashboards
- Digital photo frames
- Kiosk and wall displays
- AI-generated artwork
- Future display targets

## Architecture

Display Canvas separates visual media into three concepts:

### Sources

Where media originates:

- Home Assistant Media
- AI-generated images
- Uploaded images
- Remote URLs
- Future camera and integration sources

### Collections

Logical groups of media such as:

- Favorites
- Halloween
- Christmas
- Weather
- Local History

An image may belong to multiple collections.

### Targets

Systems that consume Display Canvas media:

- Projectivy / Overflight
- Aerial Views
- Home Assistant
- Future display integrations

## Status

Early development.
