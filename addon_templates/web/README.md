# Web Exploitation — Add-on Template

Starter scaffold for a custom web challenge. Edit, then drag the folder
onto the **Add-ons** page to import.

## What to edit

1. **`template.json`** — id, name, hint. Adjust `exposed_ports` if you
   change the Flask listening port.
2. **`app.py`** — the vulnerable web app. Common variations:
   - Add a search endpoint with reflected XSS
   - Add a download endpoint with path traversal (`../../etc/passwd`)
   - Add an upload endpoint with insufficient validation
   - Use parameterized SQL on the login but keep the bug elsewhere
3. **`Dockerfile`** — usually fine. Add more Python deps if your variant
   needs them (e.g. PyJWT for a JWT-cracking challenge).

## Flag placeholders

`flag_template` understands:
- `{challenge}` — slugified challenge name
- `{rand}`     — random hex per instance

The realized flag is passed to the container via the `CHALL_FLAG` env var.

## Import

Drag this folder onto the Add-ons page.
