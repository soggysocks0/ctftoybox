# Custom — Add-on Template

The most flexible scaffold. Use this for anything that doesn't fit neatly
into the other categories: crypto puzzles, OSINT, multi-step challenges,
language-specific challenges, etc.

## What to edit

1. **`template.json`** — id, name, description. Set `exposed_ports` if your
   challenge runs a network service; leave empty for offline-only challenges.
2. **`Dockerfile`** — replace with whatever your challenge needs. Add any
   source files alongside and `COPY` them in.
3. **`flag.txt`** — leave `{{FLAG}}` as-is; CTF Manager replaces it.

## Flag placeholders

`flag_template` understands:
- `{challenge}` — slugified challenge name
- `{rand}`     — random hex per instance

## Tips

- Keep images small. `alpine`, `-slim`, or `-bookworm-slim` bases are good.
- If your challenge needs persistent data, mount a volume — but most CTF
  challenges should be ephemeral so each player gets a fresh state.
- For multi-step challenges, consider a single container running multiple
  services via `s6-overlay` or similar, rather than docker-compose
  (CTF Manager runs single containers).

## Import

Drag this folder onto the Add-ons page.
