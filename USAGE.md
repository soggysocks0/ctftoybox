# CTFToyBox — Usage Guide

This document covers how to deploy a challenge instance, where to find
flags, hints, and READMEs, and exactly how players access each challenge
type once it's running.

---

## Prerequisites

- **CTFToyBox** installed and running
- **Docker Desktop** (Windows / macOS) or the Docker engine (Linux)
  installed and running. Challenges will generate without Docker, but you
  cannot start them until the daemon is reachable.
- For binary exploitation challenges, players will need `netcat` or
  `pwntools` on their attacking machine.

---

## Deploying a Challenge Instance

1. Open CTFToyBox and navigate to the **Instances** page from the sidebar.

2. Click the **Deploy ▾** button in the top-right corner. A dropdown
   appears with the available challenge categories.

3. Select a category. The **Deploy Wizard** opens and walks you through
   four steps:

   **Step 1 — Name**
   Give the instance a memorable name (e.g. `overflow-lab-1`). Letters,
   numbers, dashes, and underscores only. This name appears in the flag:
   `bluebox{category_overflow_lab_1_<rand>}`.

   **Step 2 — Resources**
   Allocate CPU cores, memory, and port mappings. Each category comes
   with a sensible baseline pre-filled — you can leave these as-is, unless you have some resource constraints.

   **Step 3 — Template**
   Select a challenge template from the list. The right-hand panel shows
   the template's description, learning goal, difficulty, and tags.

   **Step 4 — Review**
   Confirm your configuration, then click **Generate**. CTFToyBox writes
   the file.

   ```
   ~/.ctf_manager/instances/<instance-id>/
   ```

   A card for the new instance appears on the Instances page with the
   status **Generated**.

4. Click **▶ Run** on the instance card. CTFToyBox runs `docker build`
   then `docker run` in the background. The status box updates:

   ```
   Generated → Building… → Running
   ```

   Once the pill shows **Running** the challenge is live and accepting
   connections.

---

## Finding the README, Flag, and Hints

Every generated instance folder contains a `README.md` written for the
**organizer**, not the player. Which includes:

- The challenge description
- Build and run instructions
- The challenge flag
- A solver hint or template

### How to open it

**Option A — CTFToyBox UI**
Click **Open folder** on the instance card. Your OS file manager opens
the instance directory. Open `README.md` in any text editor.

**Option B — Storage page**
Navigate to **Storage** in the sidebar. Select the instance from the
tree on the left, then click **Open folder** or **Download as ZIP…** to
get the full bundle.

**Option C — Terminal (Linux / macOS)**
```bash
cat ~/.ctf_manager/instances/<instance-id>/README.md
```

**Option D — Terminal (Windows PowerShell)**
```powershell
Get-Content "$env:USERPROFILE\.ctf_manager\instances\<instance-id>\README.md"
```

### What's in each category's folder

| Category | Key files | Where the flag lives |
|---|---|---|
| Reverse Engineering | `chall.c`, `Dockerfile`, `README.md` | Compiled into the binary; printed on correct password |
| Binary Exploitation | `chall.c`, `flag.txt`, `Dockerfile`, `README.md` | `/flag.txt` inside the container; printed by `win()` |
| Web Exploitation | `app.py`, `Dockerfile`, `README.md` | `CHALL_FLAG` env var; returned in the login response |
| Forensics | `make_challenge.py`, `Dockerfile`, `README.md` | Inside `challenge.jpg` — EXIF comment + appended after EOI |
| Custom | `Dockerfile`, `flag.txt`, `README.md` | User-defined |

---

## Accessing a Running Challenge

The host machine's IP is whatever address your players use to reach it.
On a local network, run `ipconfig` (Windows) or `ip a` (Linux) to find
it. On a cloud VM, use the public IP.

### Reverse Engineering

RE challenges are **offline** — there is no network service. Players
copy the binary out of the running container and reverse it locally, or it can be distributed to them via the organizer.

```bash
# Find the container name — shown on the instance card as the instance id
docker ps

# Copy the binary to the current directory
docker cp ctfmgr_<instance-id>:/chall ./chall


---

### Binary Exploitation

Pwn challenges run behind `socat` on a TCP port (default **31337**).
Players connect over the network and send their exploit.

```
┌─────────────────────┐        TCP 31337        ┌──────────────────────┐
│   Player machine    │ ──────────────────────► │   Host running       │
│   (attacker)        │                         │   CTFToyBox          │
│                     │                         │   └─ Docker          │
│   nc / pwntools     │ ◄────────────────────── │     └─ socat:31337   │
└─────────────────────┘                         │       └─ ./chall     │
                                                └──────────────────────┘
```

**Connect with netcat:**
```bash
nc <host-ip> 31337
```

**Connect with pwntools:**
```python
from pwn import *
io = remote("<host-ip>", 31337)
io.interactive()
```

**If you changed the port in the wizard**, substitute that port number
everywhere `31337` appears above. The exact port mapping is visible on
the **Networking** page and on the instance card.

**Flag format:** `bluebox{pwn_<challenge-name>_<rand>}`
The flag is printed to stdout when `win()` is reached.

---

### Web Exploitation

Web challenges run a Flask application on HTTP (default **port 8080**).
Players access it in a browser or with curl.

```
┌─────────────────────┐        HTTP :8080        ┌──────────────────────┐
│   Player machine    │ ──────────────────────► │   Host running       │
│                     │                         │   CTFToyBox          │
│   Browser / curl /  │                         │   └─ Docker          │
│   Burp Suite        │ ◄────────────────────── │     └─ Flask:8080    │
└─────────────────────┘                         └──────────────────────┘
```

**Open in a browser:**
```
http://<host-ip>:8080
```

**Test with curl:**
```bash
curl http://<host-ip>:8080
```

**If you changed the port in the wizard**, substitute that port number.
The exact port mapping is visible on the **Networking** page.

**Flag format:** `bluebox{web_<challenge-name>_<rand>}`
The flag is returned inside the HTTP response when the vulnerability is
successfully exploited.

---

### Forensics

Forensics challenges are **offline** — there is no live network service.
Players copy a generated artifact (a JPEG) out of the container and
analyze it with forensics tools.

```bash
# Find the container name
docker ps

# Copy the artifact to the current directory
docker cp ctfmgr_<instance-id>:/out/challenge.jpg ./challenge.jpg

```

**Flag format:** `bluebox{for_<challenge-name>_<rand>}`

---

### Custom

Custom challenges depend entirely on the Dockerfile you provided. Check
the `README.md` in the instance folder for the access method and any
ports you configured. You can customize these yourself or have an A.I generate one for you.

If the challenge exposes a port, the same patterns above apply — connect
with `nc`, a browser, or pwntools depending on the service type.

---

## Checking Ports at a Glance

The **Networking** page in CTFToyBox lists every running instance with
its port mappings and live container status. It refreshes automatically
every 4 seconds.

You can also check directly from the terminal:

```bash
# All ports Docker is currently exposing
docker ps --format "table {{.Names}}\t{{.Ports}}"

# Ports listening on the host (Linux)
ss -tlnp

# Ports listening on the host (Windows)
netstat -ano | findstr LISTENING
```

---

## Stopping a Challenge

Click **■ Stop** on the instance card. CTFToyBox runs `docker stop` and
`docker rm` in the background. The status returns to **Stopped**.

To restart the same instance, click **▶ Run** again. The existing image
is reused — no rebuild needed.

---

## Deleting a Challenge

Click **✕** on the instance card and confirm. This:

1. Stops the running container (if any)
2. Removes the Docker image
3. Deletes the instance folder from `~/.ctf_manager/instances/`

This action is permanent. The flag for that instance is gone. If you
want to archive the files first, use **Open folder** or the **Storage**
page's **Download as ZIP…** button before deleting.

---

## Quick Reference

| Category | Network access | Default port | Flag location |
|---|---|---|---|
| Reverse Engineering | `docker cp` — offline | none | Printed by binary on correct input |
| Binary Exploitation | `nc` / pwntools — TCP | **31337** | Printed by `win()` via socat |
| Web Exploitation | Browser / curl — HTTP | **8080** | Returned in HTTP response |
| Forensics | `docker cp` — offline | none | Hidden in `challenge.jpg` |
| Custom | User-defined | User-defined | User-defined |

All flags follow the format: `bluebox{category_challengename_randomhex}`