# JARVIS OMA

JARVIS OMA is the Omarchy-facing integration layer and reference archive for
turning an Omarchy desktop into a voice-operable personal computing environment.

This folder is intentionally separate from the product-level JARVIS OS
specification. It contains the Omarchy assumptions, imported skill boundaries,
desktop-control contract, and migration notes that must remain understandable
when Omarchy changes.

## Source of truth

- [OMA master document](../../historical-plans/JARVIS%20OMA/MASTER-DOCUMENT.md)
- [Omarchy integration guide](../docs/omarchy-integration.md)
- [Omarchy voice port guide](../docs/omarchy-voice-port.md)
- [Verified system control](../docs/system-control.md)
- Bundled guides and provenance: `../jarvis_control/omarchy_guides/`

JARVIS OMA does not replace the packaged Omarchy files. User overrides belong
in user configuration, while `/usr/share/omarchy` remains read-only.
