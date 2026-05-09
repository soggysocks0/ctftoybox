"""
Windows 11 setup script generator.

Composes a single PowerShell script (`setup.ps1`) that:
  1. Refuses to run if it doesn't have admin
  2. Walks through the template's vulnerabilities, planting each one
  3. Walks through the template's defenses, enabling each one
  4. Appends each user-selected service's PowerShell fragment

Tier mapping is data-driven: which Vulnerability / Defense ids appear
in the template controls what gets emitted. The functions below are the
catalog of installable blocks.
"""

from __future__ import annotations

from system_templates.registry import SystemTemplate, Tier
from system_templates.services import LiveService


# ---------------------------------------------------------------------------
# Reusable block emitters
# ---------------------------------------------------------------------------

def _block_admin_check() -> str:
    return r"""
# --- Admin check ---------------------------------------------------------
$current = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal $current).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host '[!] This script must be run from an elevated PowerShell.' -ForegroundColor Red
    exit 1
}

Write-Host '====================================================='
Write-Host ' CTFToyBox — System Template setup'
Write-Host '====================================================='
Write-Host ''
"""


def _block_weak_user() -> str:
    return r"""
# --- Weak local user 'jdoe' ----------------------------------------------
Write-Host '[+] Creating weak local user jdoe (Password123) in Administrators'
$pw = ConvertTo-SecureString 'Password123' -AsPlainText -Force
if (Get-LocalUser -Name 'jdoe' -ErrorAction SilentlyContinue) {
    Set-LocalUser -Name 'jdoe' -Password $pw
} else {
    New-LocalUser -Name 'jdoe' -Password $pw -PasswordNeverExpires `
        -AccountNeverExpires -FullName 'John Doe' `
        -Description 'Lab user — weak credentials' | Out-Null
}
Add-LocalGroupMember -Group 'Administrators' -Member 'jdoe' -ErrorAction SilentlyContinue
"""


def _block_permissive_password_policy() -> str:
    return r"""
# --- Permissive local password policy ------------------------------------
Write-Host '[+] Setting permissive password policy (min 6, no complexity, no lockout)'
net accounts /minpwlen:6 /maxpwage:UNLIMITED /lockoutthreshold:0 | Out-Null
secedit /export /cfg $env:TEMP\secpol.cfg | Out-Null
(Get-Content $env:TEMP\secpol.cfg) -replace 'PasswordComplexity\s*=\s*\d', 'PasswordComplexity = 0' |
    Set-Content $env:TEMP\secpol.cfg
secedit /configure /db $env:WINDIR\security\local.sdb /cfg $env:TEMP\secpol.cfg /areas SECURITYPOLICY | Out-Null
Remove-Item $env:TEMP\secpol.cfg -ErrorAction SilentlyContinue
"""


def _block_guest_share() -> str:
    return r"""
# --- Guest-accessible SMB share at C:\Files ------------------------------
Write-Host '[+] Creating SMB share C:\Files (guest-accessible) + planted credentials.txt'
$path = 'C:\Files'
New-Item -ItemType Directory -Force $path | Out-Null
@'
# Internal IT note — DO NOT SHARE
backup_user : bsmith
backup_pass : Spring2025!
'@ | Out-File -Encoding ascii "$path\credentials.txt"

# Enable guest account so the share is reachable without a password
$guest = Get-LocalUser -Name 'Guest'
if ($guest.Enabled -eq $false) { Enable-LocalUser -Name 'Guest' }

if (Get-SmbShare -Name 'Files' -ErrorAction SilentlyContinue) {
    Remove-SmbShare -Name 'Files' -Force
}
New-SmbShare -Name 'Files' -Path $path -FullAccess 'Everyone' | Out-Null
"""


def _block_unquoted_service_path() -> str:
    return r"""
# --- Unquoted service path ('CTFLabSvc') ---------------------------------
Write-Host '[+] Registering custom service with unquoted path (privesc surface)'
$svcDir = 'C:\Program Files\CTFLab'
New-Item -ItemType Directory -Force $svcDir | Out-Null

# Tiny harmless service exe via cmd /c stub — we register cmd as the
# service and pass an unquoted path with spaces deliberately.
$binPath = 'C:\Program Files\CTFLab\CTFLab Runner.exe'
'echo CTFLab service stub' | Out-File -Encoding ascii "$svcDir\stub.bat"
Copy-Item "$env:WINDIR\System32\cmd.exe" "$svcDir\CTFLab Runner.exe" -Force

# Register service WITHOUT quoting the binary path
sc.exe create CTFLabSvc binPath= "$binPath /c $svcDir\stub.bat" start= demand | Out-Null
sc.exe description CTFLabSvc 'Lab service with unquoted path (CTF Manager)' | Out-Null

# Loosen ACL on the parent dir so a non-admin user can drop a 'CTFLab.exe'
$acl = Get-Acl $svcDir
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    'Authenticated Users', 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
$acl.AddAccessRule($rule)
Set-Acl -Path $svcDir -AclObject $acl
"""


def _block_autologon_remnant() -> str:
    return r"""
# --- AutoAdminLogon registry leftover (cleartext password) ---------------
Write-Host '[+] Planting cleartext AutoAdminLogon remnants in Winlogon'
$wl = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Set-ItemProperty -Path $wl -Name 'AutoAdminLogon'   -Value '0'
Set-ItemProperty -Path $wl -Name 'DefaultUserName'  -Value 'jdoe'
Set-ItemProperty -Path $wl -Name 'DefaultPassword'  -Value 'Password123'
Set-ItemProperty -Path $wl -Name 'DefaultDomainName' -Value $env:COMPUTERNAME
"""


def _block_scheduled_task_writable_script() -> str:
    return r"""
# --- SYSTEM scheduled task running a user-writable script ---------------
Write-Host '[+] Creating CTFLabHousekeep scheduled task (SYSTEM, writable script dir)'
$dir = 'C:\ProgramData\CTFLab'
New-Item -ItemType Directory -Force $dir | Out-Null
@'
# Lab housekeeping — CTF Manager
Get-Date | Out-File -Append "$env:ProgramData\CTFLab\heartbeat.log"
'@ | Out-File -Encoding ascii "$dir\housekeep.ps1"

# Loosen ACL on the script's directory so Authenticated Users can replace it
$acl = Get-Acl $dir
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    'Authenticated Users', 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
$acl.AddAccessRule($rule)
Set-Acl -Path $dir -AclObject $acl

# Re-create the task each run for idempotence
schtasks /Delete /TN CTFLabHousekeep /F 2>$null | Out-Null
schtasks /Create /SC MINUTE /MO 10 /RU SYSTEM /TN CTFLabHousekeep `
    /TR "powershell -NoProfile -ExecutionPolicy Bypass -File $dir\housekeep.ps1" /F | Out-Null
"""


# --- Defenses -------------------------------------------------------------

def _block_def_audit() -> str:
    return r"""
# --- Defense: audit policy -----------------------------------------------
Write-Host '[+] Enabling audit policy (Logon, Account Logon, Object Access, Process, Privilege)'
auditpol /set /category:'Logon/Logoff'        /success:enable /failure:enable | Out-Null
auditpol /set /category:'Account Logon'       /success:enable /failure:enable | Out-Null
auditpol /set /category:'Object Access'       /success:enable /failure:enable | Out-Null
auditpol /set /category:'Detailed Tracking'   /success:enable                 | Out-Null
auditpol /set /category:'Privilege Use'       /success:enable /failure:enable | Out-Null
"""


def _block_def_fw_basic() -> str:
    return r"""
# --- Defense: Windows Firewall (basic) -----------------------------------
Write-Host '[+] Windows Firewall: Domain/Private ON (default block inbound), Public left open for lab'
Set-NetFirewallProfile -Profile Domain,Private -Enabled True -DefaultInboundAction Block
"""


def _block_def_fw_strict() -> str:
    return r"""
# --- Defense: Windows Firewall (strict) ----------------------------------
Write-Host '[+] Windows Firewall: ALL profiles ON, default inbound block'
Set-NetFirewallProfile -All -Enabled True -DefaultInboundAction Block

# Allow SMB and RDP back in (lab needs to be reachable somehow)
foreach ($n in 'File and Printer Sharing (SMB-In)','Remote Desktop - User Mode (TCP-In)') {
    Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue |
        Set-NetFirewallRule -Enabled True -Profile Any
}
"""


def _block_def_defender() -> str:
    return r"""
# --- Defense: Microsoft Defender real-time on ----------------------------
Write-Host '[+] Microsoft Defender real-time protection ON'
Set-MpPreference -DisableRealtimeMonitoring $false
"""


def _block_def_lsa_protection() -> str:
    return r"""
# --- Defense: LSA Protection (RunAsPPL) ----------------------------------
Write-Host '[+] Enabling LSA Protection (RunAsPPL = 1) — takes effect on next reboot'
$lsa = 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa'
Set-ItemProperty -Path $lsa -Name 'RunAsPPL' -Value 1 -Type DWord
"""


def _block_def_password_policy_strong() -> str:
    return r"""
# --- Defense: strong password policy -------------------------------------
Write-Host '[+] Strong local password policy: min 12, complexity ON, lockout 5/30, history 24'
net accounts /minpwlen:12 /maxpwage:90 /lockoutthreshold:5 /lockoutwindow:30 /lockoutduration:30 /uniquepw:24 | Out-Null
secedit /export /cfg $env:TEMP\secpol.cfg | Out-Null
(Get-Content $env:TEMP\secpol.cfg) -replace 'PasswordComplexity\s*=\s*\d', 'PasswordComplexity = 1' |
    Set-Content $env:TEMP\secpol.cfg
secedit /configure /db $env:WINDIR\security\local.sdb /cfg $env:TEMP\secpol.cfg /areas SECURITYPOLICY | Out-Null
Remove-Item $env:TEMP\secpol.cfg -ErrorAction SilentlyContinue
"""


# ---------------------------------------------------------------------------
# Vuln/defense → block lookup, keyed by `Vulnerability.name`/`Defense.name`.
# Adding a new template means: add a Vulnerability/Defense in registry.py
# and a matching block here.
# ---------------------------------------------------------------------------

_VULN_BLOCKS: dict[str, callable] = {
    "Weak local user account":             _block_weak_user,
    "Permissive local password policy":    _block_permissive_password_policy,
    "Guest-accessible SMB share at C:\\Files": _block_guest_share,
    "Cleartext credentials in shared file": lambda: "",  # handled inside _block_guest_share
    "Unquoted service path":               _block_unquoted_service_path,
    "Stale AutoAdminLogon registry leftover": _block_autologon_remnant,
    "SYSTEM scheduled task running a user-writable script":
        _block_scheduled_task_writable_script,
}

_DEF_BLOCKS: dict[str, callable] = {
    "Audit policy enabled":              _block_def_audit,
    "Windows Firewall: basic profile":   _block_def_fw_basic,
    "Windows Firewall: strict":          _block_def_fw_strict,
    "Microsoft Defender real-time protection": _block_def_defender,
    "LSA Protection (RunAsPPL)":         _block_def_lsa_protection,
    "Strong local password policy":      _block_def_password_policy_strong,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_setup_script(template: SystemTemplate, services: list[LiveService]) -> str:
    """Emit the full setup.ps1 contents for a Windows template."""
    parts: list[str] = [
        "# CTFToyBox — auto-generated system template setup",
        f"# Template: {template.name}  (tier: {template.tier.display_name})",
        "# Run from an elevated PowerShell prompt on a DISPOSABLE Windows 11 VM.",
        "",
        "$ErrorActionPreference = 'Stop'",
        _block_admin_check(),
    ]

    # Vulnerabilities first, then defenses (so audit/firewall observe the
    # planting and the resulting state matches what an attacker sees).
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
            if not svc.powershell_setup.strip():
                parts.append(f"# (service '{svc.name}' has no Windows installer — skipped)")
                continue
            parts.append(f"# --- {svc.name} ---")
            parts.append(svc.powershell_setup)

    parts.append("")
    parts.append("Write-Host ''")
    parts.append("Write-Host 'Setup complete. See VULNERABILITIES.md in this folder.' -ForegroundColor Green")
    parts.append("")

    return "\n".join(parts)