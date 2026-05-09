"""
Ubuntu setup script generator.

Produces `setup.sh` that:
  1. Checks for root
  2. Plants the template's vulnerabilities
  3. Enables the template's defenses
  4. Appends each chosen service's bash fragment

Same data-driven dispatch model as the Windows generator.
"""

from __future__ import annotations

from system_templates.registry import SystemTemplate
from system_templates.services import LiveService


# ---------------------------------------------------------------------------
# Block emitters — vulnerabilities
# ---------------------------------------------------------------------------

def _block_root_check() -> str:
    return """\
# --- Root check ----------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo "[!] Run this script as root (sudo)." >&2
    exit 1
fi

echo "====================================================="
echo " CTFToyBox — System Template setup"
echo "====================================================="
echo
"""


def _block_weak_user() -> str:
    # `openssl passwd -6 Password123` => $6$... — for a real script we'd
    # generate fresh, but a fixed hash is fine for a lab and avoids
    # platform-specific openssl behavior.
    return r"""
# --- Weak user 'jdoe' (Password123) --------------------------------------
echo '[+] Creating weak user jdoe'
if ! id -u jdoe >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo,staff jdoe
fi
# A SHA-512 hash of "Password123"
echo 'jdoe:$6$ctfmgr$LnIu8rWqL8wGEJWPgYwCkn3JOJZxX0xZYxDPEaBVA2DiPOeSj3dW2I.Wt9vwEUNJxTWa9EXTJZQpPcWfSe.1y/' | chpasswd -e
"""


def _block_ssh_no_rate_limit() -> str:
    return r"""
# --- SSH password auth + no rate limiting --------------------------------
echo '[+] Permissive sshd_config (password auth on, no rate limit)'
apt-get install -y openssh-server >/dev/null
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/'  /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/'  /etc/ssh/sshd_config
sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 6/'                        /etc/ssh/sshd_config
sed -i 's/^#\?LoginGraceTime.*/LoginGraceTime 120/'                  /etc/ssh/sshd_config
systemctl enable ssh >/dev/null
systemctl restart ssh
"""


def _block_world_writable_backup() -> str:
    return r"""
# --- World-writable backup with /etc/shadow inside ----------------------
echo '[+] Planting world-writable /srv/backup with backup.tar (contains /etc/shadow)'
mkdir -p /srv/backup
tar -cf /srv/backup/backup.tar -C / etc/passwd etc/shadow 2>/dev/null
chmod 0777 /srv/backup
chmod 0666 /srv/backup/backup.tar
"""


def _block_sudo_nmap() -> str:
    return r"""
# --- Sudo NOPASSWD on nmap (GTFOBins privesc) ----------------------------
echo '[+] Adding insecure sudoers entry: jdoe -> nmap NOPASSWD'
cat > /etc/sudoers.d/99-ctfmgr-nmap <<'EOF'
jdoe ALL=(root) NOPASSWD: /usr/bin/nmap
EOF
chmod 0440 /etc/sudoers.d/99-ctfmgr-nmap
apt-get install -y nmap >/dev/null
"""


def _block_cleartext_creds() -> str:
    return r"""
# --- Cleartext credentials in /opt/app/config.ini ------------------------
echo '[+] Planting /opt/app/config.ini with cleartext DB credentials'
mkdir -p /opt/app
cat > /opt/app/config.ini <<'EOF'
[database]
host = localhost
user = app
password = CorrectHorseBatteryStaple
schema = labdata
EOF
chmod 0644 /opt/app/config.ini
"""


def _block_cron_writable() -> str:
    return r"""
# --- Root cron job running a writable script -----------------------------
echo '[+] Setting up /etc/cron.d/ctflab-housekeep -> /opt/ctflab/housekeep.sh (group-writable)'
mkdir -p /opt/ctflab
cat > /opt/ctflab/housekeep.sh <<'EOF'
#!/bin/bash
# Lab housekeeping — CTFToyBox
date >> /var/log/ctflab-heartbeat.log
EOF
chgrp staff /opt/ctflab /opt/ctflab/housekeep.sh
chmod 0775  /opt/ctflab
chmod 0775  /opt/ctflab/housekeep.sh
touch /var/log/ctflab-heartbeat.log
chmod 0666 /var/log/ctflab-heartbeat.log

cat > /etc/cron.d/ctflab-housekeep <<'EOF'
*/5 * * * * root /opt/ctflab/housekeep.sh >/dev/null 2>&1
EOF
chmod 0644 /etc/cron.d/ctflab-housekeep
"""


def _block_suid_backup_binary() -> str:
    return r"""
# --- Custom SUID-root backup binary with tar wildcard injection ----------
echo '[+] Planting /usr/local/bin/ctflab-backup (SUID root, tar wildcard injection)'
cat > /usr/local/bin/ctflab-backup <<'EOF'
#!/bin/bash
# Backs up /tmp/ctflab-backup-input/ — but doesn't sanitize argv to tar.
cd /tmp/ctflab-backup-input 2>/dev/null || mkdir -p /tmp/ctflab-backup-input
tar cf /tmp/ctflab-backup.tar *
EOF
chmod 4755 /usr/local/bin/ctflab-backup
mkdir -p /tmp/ctflab-backup-input
chmod 0777 /tmp/ctflab-backup-input
"""


# ---------------------------------------------------------------------------
# Block emitters — defenses
# ---------------------------------------------------------------------------

def _block_def_ufw() -> str:
    return r"""
# --- Defense: UFW deny-by-default ----------------------------------------
echo '[+] Enabling UFW (default deny incoming, allow ssh)'
apt-get install -y ufw >/dev/null
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable
"""


def _block_def_auditd() -> str:
    return r"""
# --- Defense: auditd with login + sudo rules -----------------------------
echo '[+] Installing auditd with basic login/sudo rules'
DEBIAN_FRONTEND=noninteractive apt-get install -y auditd >/dev/null
cat > /etc/audit/rules.d/ctflab.rules <<'EOF'
-w /var/log/lastlog       -p wa -k logins
-w /var/log/faillog       -p wa -k logins
-w /etc/sudoers           -p wa -k sudoers_changes
-w /etc/sudoers.d/        -p wa -k sudoers_changes
-w /var/log/auth.log      -p wa -k auth_log
EOF
augenrules --load >/dev/null 2>&1 || true
systemctl enable auditd >/dev/null
systemctl restart auditd
"""


def _block_def_apparmor() -> str:
    return r"""
# --- Defense: AppArmor in enforce mode -----------------------------------
echo '[+] AppArmor: enforce mode for default profiles'
apt-get install -y apparmor apparmor-utils apparmor-profiles >/dev/null
aa-enforce /etc/apparmor.d/* 2>/dev/null || true
systemctl enable apparmor >/dev/null
systemctl restart apparmor
"""


def _block_def_sshd_harden() -> str:
    return r"""
# --- Defense: hardened sshd_config ---------------------------------------
echo '[+] Hardening sshd_config (PermitRootLogin no, MaxAuthTries 3, grace 30s)'
apt-get install -y openssh-server >/dev/null
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'           /etc/ssh/sshd_config
sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/'                  /etc/ssh/sshd_config
sed -i 's/^#\?LoginGraceTime.*/LoginGraceTime 30/'             /etc/ssh/sshd_config
sed -i 's/^#\?ClientAliveInterval.*/ClientAliveInterval 300/'  /etc/ssh/sshd_config
systemctl restart ssh
"""


def _block_def_fail2ban() -> str:
    return r"""
# --- Defense: fail2ban with sshd jail ------------------------------------
echo '[+] Installing fail2ban (sshd jail: 5 failures = 10 min ban)'
apt-get install -y fail2ban >/dev/null
cat > /etc/fail2ban/jail.d/ctflab.local <<'EOF'
[sshd]
enabled  = true
port     = ssh
maxretry = 5
bantime  = 600
findtime = 600
EOF
systemctl enable fail2ban >/dev/null
systemctl restart fail2ban
"""


def _block_def_password_policy() -> str:
    return r"""
# --- Defense: strong PAM password policy ---------------------------------
echo '[+] Tightening PAM password policy (pam_pwquality + login.defs)'
apt-get install -y libpam-pwquality >/dev/null
if ! grep -q 'pam_pwquality.so' /etc/pam.d/common-password; then
    sed -i '/pam_unix.so/i password requisite pam_pwquality.so retry=3 minlen=12 dcredit=-1 ucredit=-1 ocredit=-1 lcredit=-1' /etc/pam.d/common-password
fi
sed -i 's/^PASS_MAX_DAYS.*/PASS_MAX_DAYS 90/' /etc/login.defs
sed -i 's/^PASS_MIN_DAYS.*/PASS_MIN_DAYS 1/'  /etc/login.defs
"""


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

_VULN_BLOCKS: dict[str, callable] = {
    "Weak default user":                          _block_weak_user,
    "SSH password auth + no rate-limiting":       _block_ssh_no_rate_limit,
    "World-writable backup directory":            _block_world_writable_backup,
    "Insecure sudoers entry — nmap (NOPASSWD)":   _block_sudo_nmap,
    "Cleartext credentials in /opt/app/config.ini": _block_cleartext_creds,
    "Root cron job running a user-writable script": _block_cron_writable,
    "Custom SUID binary in /usr/local/bin":       _block_suid_backup_binary,
}

_DEF_BLOCKS: dict[str, callable] = {
    "UFW with deny-by-default":                _block_def_ufw,
    "auditd enabled with login + sudo rules":  _block_def_auditd,
    "AppArmor in enforce mode for default profiles": _block_def_apparmor,
    "Hardened sshd_config":                    _block_def_sshd_harden,
    "fail2ban with sshd jail":                 _block_def_fail2ban,
    "Strong PAM password policy":              _block_def_password_policy,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_setup_script(template: SystemTemplate, services: list[LiveService]) -> str:
    parts: list[str] = [
        "#!/usr/bin/env bash",
        "# CTF Manager — auto-generated system template setup",
        f"# Template: {template.name}  (tier: {template.tier.display_name})",
        "# Run as root on a DISPOSABLE Ubuntu VM. Do NOT run on a daily driver.",
        "",
        "set -uo pipefail",
        "export DEBIAN_FRONTEND=noninteractive",
        _block_root_check(),
    ]

    if template.vulnerabilities:
        parts.append("# ============== Vulnerabilities ==============")
        for v in template.vulnerabilities:
            block_fn = _VULN_BLOCKS.get(v.name)
            if block_fn is None:
                parts.append(f"# (no installer registered for vuln '{v.name}' — skipped)")
                continue
            parts.append(block_fn())

    if template.defenses:
        parts.append("# ================= Defenses ==================")
        for d in template.defenses:
            block_fn = _DEF_BLOCKS.get(d.name)
            if block_fn is None:
                parts.append(f"# (no installer registered for defense '{d.name}' — skipped)")
                continue
            parts.append(block_fn())

    if services:
        parts.append("# =============== Live services ===============")
        for svc in services:
            if not svc.bash_setup.strip():
                parts.append(f"# (service '{svc.name}' has no Linux installer — skipped)")
                continue
            parts.append(f"# --- {svc.name} ---")
            parts.append(svc.bash_setup)

    parts.append("")
    parts.append("echo")
    parts.append('echo "Setup complete. See VULNERABILITIES.md in this folder."')
    parts.append("")

    return "\n".join(parts)