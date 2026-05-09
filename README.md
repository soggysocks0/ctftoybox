# CTFToyBox

> A CTFd-inspired desktop app for easy deployment and management of CTF challenge instances.

<img width="1202" height="782" alt="menu1" src="https://github.com/user-attachments/assets/483722ec-9495-4c35-82fb-dc641ca5d251" />

## Features
- Runs on local systems, perfect for the classroom, clubs or competitions
- Easy, accessible and fast
- Easily deploy CTF challenges (RE / Pwn / Web / Forensics / Custom) via Docker
- Generate vulnerable system templates (Win11 / Ubuntu, easy / med / hard)
- Live container monitoring with audit logs
- Add custom user-made CTF/Image challenges and templates
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
