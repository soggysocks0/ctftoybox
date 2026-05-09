"""
Registry of system templates.

Six templates: {Windows 11, Ubuntu} × {easy, medium, hard}.

Each template lists the *vulnerabilities* it plants and the *defenses* it
enables. The actual script generation lives in `system_templates.generators`;
this file is data-only so the UI can render menu rows without importing
generator code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TargetOS(str, Enum):
    WINDOWS_11    = "windows_11"
    UBUNTU        = "ubuntu_desktop"
    UBUNTU_SERVER = "ubuntu_server"

    @property
    def display_name(self) -> str:
        return {
            TargetOS.WINDOWS_11:    "Windows 11",
            TargetOS.UBUNTU:        "Ubuntu (Desktop)",
            TargetOS.UBUNTU_SERVER: "Ubuntu Server",
        }[self]

    @property
    def shell(self) -> str:
        return "powershell" if self is TargetOS.WINDOWS_11 else "bash"


class Tier(str, Enum):
    EASY   = "easy"
    MEDIUM = "medium"
    HARD   = "hard"

    @property
    def display_name(self) -> str:
        return {
            Tier.EASY:   "Easy",
            Tier.MEDIUM: "Medium",
            Tier.HARD:   "Hard",
        }[self]


# ---------------------------------------------------------------------------
# Sub-records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Vulnerability:
    """A single weakness planted by a template script."""
    name:    str
    detail:  str            # what gets configured + how to spot/exploit
    cwe:     str = ""       # optional CWE reference for the curious

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Defense:
    """A defensive control enabled by the template (raises difficulty)."""
    name:    str
    detail:  str

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Top-level template
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SystemTemplate:
    id:               str         # stable slug
    name:             str         # display name
    target_os:        TargetOS
    tier:             Tier
    summary:          str         # one-line for the menu
    description:      str         # longer paragraph for the dialog

    vulnerabilities:  tuple[Vulnerability, ...]
    defenses:         tuple[Defense, ...] = ()

    # Service ids (from system_templates.services) that are *eligible* to be
    # added on top of this template. The UI renders these as checkboxes; the
    # user picks what they want.
    compatible_services: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Reusable vulnerability + defense pieces
# ---------------------------------------------------------------------------

# --- Windows ---
_W_WEAK_LOCAL_USER = Vulnerability(
    name="Weak local user account",
    detail=(
        "A second local account 'jdoe' with password 'Password123' and "
        "membership in the Administrators group. Quickly cracked by any "
        "credential-spray and grants full local control."
    ),
    cwe="CWE-521",
)
_W_PERMISSIVE_PASSWORD_POLICY = Vulnerability(
    name="Permissive local password policy",
    detail=(
        "Minimum length: 6, complexity: off, lockout threshold: never. "
        "Visible via `net accounts`; lets brute-force run unbounded."
    ),
    cwe="CWE-521",
)
_W_GUEST_SHARE = Vulnerability(
    name="Guest-accessible SMB share at C:\\Files",
    detail=(
        "Share 'Files' is configured for guest read/write. Discoverable "
        "via `net view \\\\target` from a peer host. Contains a planted "
        "credentials.txt for chained access."
    ),
    cwe="CWE-284",
)
_W_CLEARTEXT_CREDS_IN_FILE = Vulnerability(
    name="Cleartext credentials in shared file",
    detail=(
        "credentials.txt placed inside the shared folder names another "
        "local user + password. Mirrors common 'IT password notes' leaks."
    ),
    cwe="CWE-256",
)
_W_UNQUOTED_SERVICE_PATH = Vulnerability(
    name="Unquoted service path",
    detail=(
        "A custom service 'CTFLabSvc' is registered with a binPath that "
        "contains spaces and is not quoted. A user with write access to "
        "C:\\Program Files\\CTFLab\\ can drop a malicious 'CTFLab.exe' "
        "and Windows will launch it as SYSTEM on service start."
    ),
    cwe="CWE-428",
)
_W_AUTOLOGON_REMNANT = Vulnerability(
    name="Stale AutoAdminLogon registry leftover",
    detail=(
        "Registry keys under Winlogon retain a previous admin's "
        "DefaultPassword in cleartext from a discontinued unattended-setup "
        "process. Easy `reg query` find."
    ),
    cwe="CWE-256",
)
_W_SCHEDULED_TASK_WRITABLE_SCRIPT = Vulnerability(
    name="SYSTEM scheduled task running a user-writable script",
    detail=(
        "'CTFLabHousekeep' runs C:\\ProgramData\\CTFLab\\housekeep.ps1 as "
        "SYSTEM every 10 minutes. The script's directory is writable by "
        "Authenticated Users — replace contents, wait 10 min, get SYSTEM."
    ),
    cwe="CWE-732",
)

# --- Linux ---
_L_WEAK_USER = Vulnerability(
    name="Weak default user",
    detail=(
        "User 'jdoe' (uid 1010) with password 'Password123', shell /bin/bash. "
        "Listed in /etc/passwd; easily found via SSH bruteforce or "
        "credential-spray."
    ),
    cwe="CWE-521",
)
_L_NO_LOGIN_BANNER_NO_RATE_LIMIT = Vulnerability(
    name="SSH password auth + no rate-limiting",
    detail=(
        "PasswordAuthentication yes, MaxAuthTries 6, LoginGraceTime 120. "
        "No fail2ban or pam_tally. Allows sustained brute-force."
    ),
    cwe="CWE-307",
)
_L_WORLD_WRITABLE_BACKUP = Vulnerability(
    name="World-writable backup directory",
    detail=(
        "/srv/backup is mode 0777 with a backup.tar containing /etc/shadow "
        "(readable by all). Hash crack-and-pivot scenario."
    ),
    cwe="CWE-732",
)
_L_SUDO_NMAP = Vulnerability(
    name="Insecure sudoers entry — nmap (NOPASSWD)",
    detail=(
        "jdoe can run `sudo nmap` without a password. nmap's interactive "
        "mode (--interactive on old) or NSE script execution leads to a "
        "root shell — classic GTFOBins."
    ),
    cwe="CWE-250",
)
_L_CLEARTEXT_CREDS = Vulnerability(
    name="Cleartext credentials in /opt/app/config.ini",
    detail=(
        "Config file readable by all users contains DB credentials. "
        "Pivot point for the optional MySQL service."
    ),
    cwe="CWE-256",
)
_L_CRON_WRITABLE = Vulnerability(
    name="Root cron job running a user-writable script",
    detail=(
        "/etc/cron.d/ctflab-housekeep runs /opt/ctflab/housekeep.sh as "
        "root every 5 minutes; script lives in a directory writable by "
        "the 'staff' group, which jdoe is in. Classic privesc."
    ),
    cwe="CWE-732",
)
_L_SUID_BACKUP_BINARY = Vulnerability(
    name="Custom SUID binary in /usr/local/bin",
    detail=(
        "/usr/local/bin/ctflab-backup is owned root with mode 4755 and "
        "shells out to `tar` without sanitizing arguments — wildcard "
        "injection into root-owned tar gives root file read/write."
    ),
    cwe="CWE-78",
)


# --- Defenses (per tier) ---
_DEF_WIN_AUDIT = Defense(
    name="Audit policy enabled",
    detail="auditpol enables Logon, Account Logon, Object Access, "
           "Process Creation, Privilege Use. Recon is logged.",
)
_DEF_WIN_FW_BASIC = Defense(
    name="Windows Firewall: basic profile",
    detail="Domain/Private profiles ON, default inbound block. Public "
           "profile keeps SMB/RDP open for the lab.",
)
_DEF_WIN_FW_STRICT = Defense(
    name="Windows Firewall: strict",
    detail="All profiles ON, only opted-in services exposed (SMB, RDP, "
           "and any service the user enabled).",
)
_DEF_WIN_DEFENDER = Defense(
    name="Microsoft Defender real-time protection",
    detail="Real-time protection left enabled. Attacks must use LOLBins / "
           "amsi-bypass tactics rather than dropping plain malware.",
)
_DEF_WIN_LSA_PROT = Defense(
    name="LSA Protection (RunAsPPL)",
    detail="LSASS runs as a protected process. Naïve mimikatz is denied; "
           "attackers must use PPL-bypass or different tactics.",
)
_DEF_WIN_PASSWORD_POLICY = Defense(
    name="Strong local password policy",
    detail="Min length 12, complexity on, lockout 5/30min, history 24.",
)

_DEF_LINUX_UFW = Defense(
    name="UFW with deny-by-default",
    detail="UFW enabled, defaults: deny incoming / allow outgoing. Only "
           "SSH and any opted-in services are allowed in.",
)
_DEF_LINUX_AUDITD = Defense(
    name="auditd enabled with login + sudo rules",
    detail="Logs to /var/log/audit/audit.log. Catches lazy recon.",
)
_DEF_LINUX_APPARMOR = Defense(
    name="AppArmor in enforce mode for default profiles",
    detail="Confines tunables; doesn't directly block the lab vulns but "
           "limits naïve LD_PRELOAD / shared-library tricks.",
)
_DEF_LINUX_SSHD_HARDEN = Defense(
    name="Hardened sshd_config",
    detail="PermitRootLogin no, MaxAuthTries 3, LoginGraceTime 30, "
           "ClientAliveInterval 300. Brute-force becomes much slower.",
)
_DEF_LINUX_FAIL2BAN = Defense(
    name="fail2ban with sshd jail",
    detail="5 failed SSH logins = 10-minute IP ban. Spray attacks have "
           "to be paced or rotated across source IPs.",
)
_DEF_LINUX_PASSWORD_POLICY = Defense(
    name="Strong PAM password policy",
    detail="pam_pwquality with minlen 12, dcredit/ucredit/ocredit set; "
           "/etc/login.defs maxdays 90, mindays 1.",
)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

# Service IDs come from system_templates/services.py
_WIN_COMPATIBLE_SERVICES = ("apache", "nginx", "mysql", "ftp_iis", "samba_win")
_LIN_COMPATIBLE_SERVICES = ("apache", "nginx", "mysql", "ftp_vsftpd", "samba")


WIN11_EASY = SystemTemplate(
    id="win11-office-easy",
    name="Windows 11 — Standard Office PC (Easy)",
    target_os=TargetOS.WINDOWS_11,
    tier=Tier.EASY,
    summary="Average office workstation: weak passwords, guest SMB share, minimal hardening.",
    description=(
        "Mimics a typical small-business workstation set up by a busy IT "
        "admin. Real local accounts with weak passwords, a careless SMB "
        "share, and a credentials file dropped inside it."
    ),
    vulnerabilities=(
        _W_WEAK_LOCAL_USER,
        _W_PERMISSIVE_PASSWORD_POLICY,
        _W_GUEST_SHARE,
        _W_CLEARTEXT_CREDS_IN_FILE,
    ),
    defenses=(),  # easy = no extra defenses on top of Windows defaults
    compatible_services=_WIN_COMPATIBLE_SERVICES,
)

WIN11_MEDIUM = SystemTemplate(
    id="win11-workstation-med",
    name="Windows 11 — Hardened Workstation (Medium)",
    target_os=TargetOS.WINDOWS_11,
    tier=Tier.MEDIUM,
    summary="Decent security: audit logging, basic firewall, but still has misconfigured services.",
    description=(
        "An IT-managed workstation. Defender + audit policy are on, "
        "passwords are stronger, but a sloppy custom service install "
        "leaves an unquoted-path privesc, and a stale unattended-setup "
        "left credentials in the registry."
    ),
    vulnerabilities=(
        _W_UNQUOTED_SERVICE_PATH,
        _W_AUTOLOGON_REMNANT,
        _W_GUEST_SHARE,            # share still exists, but Defender + audit are watching
    ),
    defenses=(
        _DEF_WIN_AUDIT,
        _DEF_WIN_FW_BASIC,
        _DEF_WIN_DEFENDER,
    ),
    compatible_services=_WIN_COMPATIBLE_SERVICES,
)

WIN11_HARD = SystemTemplate(
    id="win11-datacenter-hard",
    name="Windows 11 — Datacenter-Grade Server (Hard)",
    target_os=TargetOS.WINDOWS_11,
    tier=Tier.HARD,
    summary="High-security policy: LSA protection, strict firewall, audit logging — only one subtle privesc.",
    description=(
        "What a hardened Windows server should look like. The only "
        "remaining hole is a SYSTEM scheduled task whose script lives in "
        "a directory the lab user can write to. Defenses make recon "
        "noisy and credential-stealing painful."
    ),
    vulnerabilities=(
        _W_SCHEDULED_TASK_WRITABLE_SCRIPT,
    ),
    defenses=(
        _DEF_WIN_PASSWORD_POLICY,
        _DEF_WIN_AUDIT,
        _DEF_WIN_FW_STRICT,
        _DEF_WIN_DEFENDER,
        _DEF_WIN_LSA_PROT,
    ),
    compatible_services=_WIN_COMPATIBLE_SERVICES,
)

UBUNTU_EASY = SystemTemplate(
    id="ubuntu-office-easy",
    name="Ubuntu Desktop — Standard Office PC (Easy)",
    target_os=TargetOS.UBUNTU,
    tier=Tier.EASY,
    summary="Average office Linux box: weak SSH, world-writable backup, no rate-limiting.",
    description=(
        "An Ubuntu desktop set up by a developer who left the door open. "
        "Password SSH, world-writable /srv/backup with /etc/shadow inside "
        "an unguarded archive, and a weak local user."
    ),
    vulnerabilities=(
        _L_WEAK_USER,
        _L_NO_LOGIN_BANNER_NO_RATE_LIMIT,
        _L_WORLD_WRITABLE_BACKUP,
    ),
    defenses=(),
    compatible_services=_LIN_COMPATIBLE_SERVICES,
)

UBUNTU_MEDIUM = SystemTemplate(
    id="ubuntu-workstation-med",
    name="Ubuntu Desktop — Hardened Workstation (Medium)",
    target_os=TargetOS.UBUNTU,
    tier=Tier.MEDIUM,
    summary="UFW + auditd + sshd hardening, but a sudoers slip leaves nmap-as-root.",
    description=(
        "An IT-managed Ubuntu desktop. UFW and auditd are on, sshd is "
        "tightened, but a single careless sudoers entry hands attackers "
        "a clean GTFOBins root via nmap, plus cleartext DB credentials "
        "in /opt/app/config.ini."
    ),
    vulnerabilities=(
        _L_SUDO_NMAP,
        _L_CLEARTEXT_CREDS,
    ),
    defenses=(
        _DEF_LINUX_UFW,
        _DEF_LINUX_AUDITD,
        _DEF_LINUX_SSHD_HARDEN,
    ),
    compatible_services=_LIN_COMPATIBLE_SERVICES,
)

UBUNTU_SERVER_HARD = SystemTemplate(
    id="ubuntu-datacenter-hard",
    name="Ubuntu Server — Datacenter-Grade Server (Hard)",
    target_os=TargetOS.UBUNTU_SERVER,
    tier=Tier.HARD,
    summary="Full hardening: UFW, auditd, AppArmor, fail2ban — one subtle SUID misuse.",
    description=(
        "A production-grade Ubuntu server. Almost everything is right. "
        "The only remaining hole is a custom SUID-root backup binary "
        "with a `tar` wildcard injection bug; a root cron job re-creates "
        "it on every boot, so casual cleanup doesn't help."
    ),
    vulnerabilities=(
        _L_SUID_BACKUP_BINARY,
        _L_CRON_WRITABLE,
    ),
    defenses=(
        _DEF_LINUX_PASSWORD_POLICY,
        _DEF_LINUX_UFW,
        _DEF_LINUX_AUDITD,
        _DEF_LINUX_APPARMOR,
        _DEF_LINUX_SSHD_HARDEN,
        _DEF_LINUX_FAIL2BAN,
    ),
    compatible_services=_LIN_COMPATIBLE_SERVICES,
)


REGISTRY: tuple[SystemTemplate, ...] = (
    WIN11_EASY,
    UBUNTU_EASY,
    WIN11_MEDIUM,
    UBUNTU_MEDIUM,
    WIN11_HARD,
    UBUNTU_SERVER_HARD,
)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_template(template_id: str) -> SystemTemplate | None:
    for t in REGISTRY:
        if t.id == template_id:
            return t
    return None