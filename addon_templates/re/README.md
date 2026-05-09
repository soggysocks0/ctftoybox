# Reverse Engineering — Add-on Template

This folder is a starter scaffold for a custom RE challenge. Edit it to
match your scenario, then drag the whole folder onto the **Add-ons** page
to register it as a template available in the deploy wizard.

## What to edit

1. **`template.json`** — challenge metadata. Change at minimum:
   - `id` (must be unique across your local templates)
   - `name`, `short_desc`, `learning_goal`, `hint`
   - `flag_template` if you want a different flag format
2. **`chall.c`** — the actual challenge source. Replace `password` and
   the welcome / success / failure text. The `{{FLAG}}` placeholder is
   filled in by CTF Manager at deploy time.
3. **`Dockerfile`** — usually fine as-is for a C crackme. Tweak compile
   flags if you want the binary to be stripped, PIE-enabled, etc.

## Flag placeholders

Inside `flag_template`:
- `{challenge}` — replaced by the slugified challenge name at deploy time
- `{rand}`     — replaced with random hex so each instance has a unique flag

## Import

Drag this folder onto the Add-ons page in CTF Manager. Once imported, your
template appears in the deploy wizard alongside the built-in ones.
