# CTFToyBox

> A CTFd-inspired desktop app for deploying and managing CTF challenge instances.

[screenshot here — see "Screenshots" note below]

## Features
- Deploy CTF challenges (RE / Pwn / Web / Forensics / Custom) via Docker
- Generate vulnerable system templates (Win11 / Ubuntu, easy / med / hard)
- Live container monitoring with audit logs
- Cross-platform (Windows / Linux)
- Dark and light themes

## Install

### Windows
Download `CTFToyBox.exe` from the [latest release](https://github.com/soggysocks0/ctftoybox/releases/latest)
and double-click.

### Ubuntu / Debian
Download `ctftoybox_*.deb` and:
```bash
sudo apt install ./ctftoybox_0.1.0_amd64.deb
```

### Other Linux
Download `CTFToyBox`, `chmod +x`, run.

## Requires
- Docker (only for the Run/Stop actions on challenges; everything else works without it)

## Building from source
See [packaging/README.md](packaging/README.md).

## License
MIT