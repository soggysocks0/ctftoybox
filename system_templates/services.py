"""
Live services that can be layered on top of a system template.

Each LiveService describes:
  - its display name + brief description
  - which OS families it supports
  - script fragments that get appended to the master setup script

The fragments are intentionally vulnerable-by-default to fit the lab
theme: default credentials, directory listing on, anonymous FTP, etc.

A user picking 'apache' on a Linux template gets a working Apache that's
deliberately weak; on a Windows template they get IIS configured the
same way.

The vulns each service plants are listed here too so the generated
VULNERABILITIES.md is complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from system_templates.registry import TargetOS, Vulnerability


@dataclass(frozen=True)
class LiveService:
    id:           str
    name:         str
    summary:      str

    # Which OS targets this service supports. We carry separate POSIX/Windows
    # script fragments so one LiveService entry can serve both worlds.
    supported_os: tuple[TargetOS, ...]

    # Vulnerabilities that adding this service introduces.
    vulnerabilities: tuple[Vulnerability, ...] = ()

    # Bash fragment, expanded into the linux setup.sh.
    bash_setup:        str = ""
    # PowerShell fragment, expanded into the Windows setup.ps1.
    powershell_setup:  str = ""


# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------

_APACHE = LiveService(
    id="apache",
    name="Apache HTTP Server",
    summary="Apache 2.4 with directory listing on and a leftover .git/ in the docroot.",
    supported_os=(TargetOS.WINDOWS_11, TargetOS.UBUNTU, TargetOS.UBUNTU_SERVER),
    vulnerabilities=(
        Vulnerability(
            name="Apache directory listing enabled",
            detail="Options +Indexes left on the default vhost. Browsing "
                   "/backup/ exposes archive files.",
            cwe="CWE-548",
        ),
        Vulnerability(
            name="Stale .git/ directory in webroot",
            detail="A pruned-but-leftover .git directory is reachable at "
                   "/.git/ — git-dumper recovers historical source.",
            cwe="CWE-538",
        ),
    ),
    bash_setup="""\
echo '[+] Installing Apache (vulnerable demo config)'
apt-get install -y apache2 >/dev/null
cat > /etc/apache2/sites-available/000-default.conf <<'EOF'
<VirtualHost *:80>
    ServerAdmin admin@example.local
    DocumentRoot /var/www/html
    <Directory /var/www/html>
        Options +Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>
    ErrorLog /var/log/apache2/error.log
    CustomLog /var/log/apache2/access.log combined
</VirtualHost>
EOF

# Plant a stale .git/ leftover (just enough to be obvious in CTF tooling)
mkdir -p /var/www/html/.git/objects /var/www/html/.git/refs/heads
echo 'ref: refs/heads/main' > /var/www/html/.git/HEAD
echo '[core]' > /var/www/html/.git/config
echo '    repositoryformatversion = 0' >> /var/www/html/.git/config
chmod -R o+rX /var/www/html/.git

# A backup archive someone forgot
mkdir -p /var/www/html/backup
echo 'archived 2024-Q3 — DO NOT COMMIT' > /var/www/html/backup/README.txt
echo 'db_user=app' > /var/www/html/backup/.env.bak
echo 'db_pass=hunter2-not-the-real-one' >> /var/www/html/backup/.env.bak
chown -R www-data:www-data /var/www/html

systemctl enable apache2 >/dev/null
systemctl restart apache2
echo '    → Apache up on http://<host>/  (lab vulns: directory listing + .git/ leak)'
""",
    powershell_setup=r"""
Write-Host '[+] Installing IIS as the Apache stand-in (vulnerable demo config)'
Install-WindowsFeature -Name Web-Server, Web-Mgmt-Console -IncludeManagementTools | Out-Null

# Enable directory browsing
& "$env:SystemRoot\system32\inetsrv\appcmd.exe" set config "Default Web Site" `
    /section:directoryBrowse /enabled:true | Out-Null

# Plant the .git/ leftover and backup folder
$root = 'C:\inetpub\wwwroot'
New-Item -Force -ItemType Directory "$root\.git\objects"   | Out-Null
New-Item -Force -ItemType Directory "$root\.git\refs\heads" | Out-Null
'ref: refs/heads/main' | Out-File -Encoding ascii "$root\.git\HEAD"
'[core]'                | Out-File -Encoding ascii "$root\.git\config"
'    repositoryformatversion = 0' | Out-File -Append -Encoding ascii "$root\.git\config"

New-Item -Force -ItemType Directory "$root\backup" | Out-Null
'archived 2024-Q3 — DO NOT COMMIT'         | Out-File -Encoding ascii "$root\backup\README.txt"
"db_user=app`r`ndb_pass=hunter2-not-the-real-one" | Out-File -Encoding ascii "$root\backup\.env.bak"

Write-Host '    -> IIS on http://<host>/ (lab vulns: directory browsing + .git/ leak)'
""",
)


_NGINX = LiveService(
    id="nginx",
    name="Nginx",
    summary="Nginx with autoindex on and a backup file accidentally left as plain text.",
    supported_os=(TargetOS.UBUNTU, TargetOS.UBUNTU_SERVER),  # Nginx on Win is unusual; skip.
    vulnerabilities=(
        Vulnerability(
            name="Nginx autoindex enabled",
            detail="autoindex on; for /share/ exposes file listings.",
            cwe="CWE-548",
        ),
        Vulnerability(
            name="Editor backup file in webroot (config.php~)",
            detail="A vim swap-style backup of a config file is served as "
                   "plaintext, leaking DB credentials.",
            cwe="CWE-538",
        ),
    ),
    bash_setup="""\
echo '[+] Installing nginx (vulnerable demo config)'
apt-get install -y nginx >/dev/null
cat > /etc/nginx/sites-available/default <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root /var/www/html;
    index index.html;
    server_name _;

    location / {
        try_files $uri $uri/ =404;
    }

    location /share/ {
        autoindex on;
    }
}
EOF

mkdir -p /var/www/html/share
echo '<h1>Lab nginx</h1>' > /var/www/html/index.html
echo 'shared notes — internal only' > /var/www/html/share/README.txt

# Editor backup leak — the kind of thing scanners pick up immediately.
cat > /var/www/html/config.php <<'EOF'
<?php /* live config — do not edit on disk */ ?>
EOF
cat > /var/www/html/config.php~ <<'EOF'
<?php
$db_host = 'localhost';
$db_user = 'app';
$db_pass = 'CorrectHorseBatteryStaple';   // TODO rotate
EOF
chown -R www-data:www-data /var/www/html

systemctl enable nginx >/dev/null
systemctl restart nginx
echo '    → nginx up on http://<host>/  (lab vulns: autoindex + config.php~ leak)'
""",
    powershell_setup="",
)


_MYSQL = LiveService(
    id="mysql",
    name="MySQL / MariaDB",
    summary="MySQL with a default 'app' user and a weak password matching the cleartext config.",
    supported_os=(TargetOS.WINDOWS_11, TargetOS.UBUNTU, TargetOS.UBUNTU_SERVER),
    vulnerabilities=(
        Vulnerability(
            name="MySQL default app user with weak password",
            detail="User 'app'@'%' with password 'CorrectHorseBatteryStaple' "
                   "(matches the cleartext config files planted by other "
                   "components). Network-listening on 3306 if the firewall "
                   "allows it.",
            cwe="CWE-521",
        ),
    ),
    bash_setup="""\
echo '[+] Installing MariaDB (vulnerable demo config)'
DEBIAN_FRONTEND=noninteractive apt-get install -y mariadb-server >/dev/null
systemctl enable mariadb >/dev/null
systemctl start mariadb

mysql -u root <<'EOF'
CREATE DATABASE IF NOT EXISTS labdata;
CREATE USER IF NOT EXISTS 'app'@'%' IDENTIFIED BY 'CorrectHorseBatteryStaple';
GRANT ALL PRIVILEGES ON labdata.* TO 'app'@'%';
FLUSH PRIVILEGES;
EOF

# Allow remote connections (it's a lab)
sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf 2>/dev/null || true
systemctl restart mariadb
echo '    → MariaDB on tcp/3306, user app / CorrectHorseBatteryStaple'
""",
    powershell_setup=r"""
Write-Host '[+] Skipping MySQL on Windows — install MySQL Community manually if desired.'
Write-Host '    A note has been added to VULNERABILITIES.md describing the intended weak credentials.'
""",
)


_FTP_VSFTPD = LiveService(
    id="ftp_vsftpd",
    name="vsftpd (Anonymous-readable)",
    summary="vsftpd with anonymous read enabled and a planted leftover archive.",
    supported_os=(TargetOS.UBUNTU, TargetOS.UBUNTU_SERVER),
    vulnerabilities=(
        Vulnerability(
            name="Anonymous FTP read access",
            detail="vsftpd configured with anonymous_enable=YES; "
                   "/srv/ftp/anon/ contains a backup archive.",
            cwe="CWE-285",
        ),
    ),
    bash_setup="""\
echo '[+] Installing vsftpd (anonymous read enabled — lab use only)'
apt-get install -y vsftpd >/dev/null
mkdir -p /srv/ftp/anon
echo 'snapshot 2024-09 — for IT use' > /srv/ftp/anon/README.txt
tar -cf /srv/ftp/anon/snapshot.tar -C /etc passwd 2>/dev/null
chown -R ftp:ftp /srv/ftp/anon || chown -R nobody:nogroup /srv/ftp/anon

cat > /etc/vsftpd.conf <<'EOF'
listen=YES
listen_ipv6=NO
anonymous_enable=YES
anon_root=/srv/ftp/anon
local_enable=YES
write_enable=NO
dirmessage_enable=YES
xferlog_enable=YES
connect_from_port_20=YES
secure_chroot_dir=/var/run/vsftpd/empty
pam_service_name=vsftpd
EOF

systemctl enable vsftpd >/dev/null
systemctl restart vsftpd
echo '    → vsftpd up; anonymous@<host>:21 reads /srv/ftp/anon'
""",
    powershell_setup="",
)


_FTP_IIS = LiveService(
    id="ftp_iis",
    name="IIS FTP (Anonymous-readable)",
    summary="IIS FTP site with anonymous read of C:\\ftp\\anon and a planted archive.",
    supported_os=(TargetOS.WINDOWS_11,),
    vulnerabilities=(
        Vulnerability(
            name="IIS FTP anonymous read",
            detail="FTP site bound on tcp/21 with anonymous read of "
                   "C:\\ftp\\anon. Archive 'snapshot.zip' planted inside.",
            cwe="CWE-285",
        ),
    ),
    bash_setup="",
    powershell_setup=r"""
Write-Host '[+] Installing IIS FTP role'
Install-WindowsFeature -Name Web-Ftp-Server -IncludeAllSubFeature | Out-Null
Import-Module WebAdministration

$ftpRoot = 'C:\ftp\anon'
New-Item -ItemType Directory -Force $ftpRoot | Out-Null
'snapshot 2024-09 — for IT use' | Out-File -Encoding ascii "$ftpRoot\README.txt"

# Plant a zip-shaped placeholder
Compress-Archive -Force -Path "$env:WINDIR\System32\drivers\etc\hosts" `
    -DestinationPath "$ftpRoot\snapshot.zip"

if (-not (Get-WebSite -Name 'LabFTP' -ErrorAction SilentlyContinue)) {
    New-WebFtpSite -Name 'LabFTP' -Port 21 -PhysicalPath $ftpRoot | Out-Null
}
Set-ItemProperty 'IIS:\Sites\LabFTP' -Name 'ftpServer.security.authentication.anonymousAuthentication.enabled' -Value $true
Set-WebConfigurationProperty -Filter '/system.ftpServer/security/authorization' `
    -Name '.' -Value @{accessType='Allow';users='*';permissions='Read'} `
    -PSPath 'IIS:\' -Location 'LabFTP'

Write-Host '    -> IIS FTP up on tcp/21; anonymous read of C:\ftp\anon\'
""",
)


_SAMBA = LiveService(
    id="samba",
    name="Samba (Linux)",
    summary="Samba with a guest-readable share at /srv/samba/public.",
    supported_os=(TargetOS.UBUNTU, TargetOS.UBUNTU_SERVER),
    vulnerabilities=(
        Vulnerability(
            name="Samba guest-accessible share",
            detail="Share 'public' allows guest read. Cross-protocol "
                   "access to lab files. Visible via `smbclient -L //host`.",
            cwe="CWE-284",
        ),
    ),
    bash_setup=r"""echo '[+] Installing Samba with a guest-readable share'
apt-get install -y samba >/dev/null
mkdir -p /srv/samba/public
echo 'lab share — keep small files only' > /srv/samba/public/README.txt
chmod 0777 /srv/samba/public

# Append our lab share to smb.conf (idempotent-ish)
if ! grep -q '\[public\]' /etc/samba/smb.conf; then
cat >> /etc/samba/smb.conf <<'EOF'

[public]
   path = /srv/samba/public
   browseable = yes
   read only = no
   guest ok = yes
   create mask = 0664
   directory mask = 0775
EOF
fi

# Allow guest mappings (lab only)
if ! grep -q 'map to guest = Bad User' /etc/samba/smb.conf; then
    sed -i '/^\[global\]/a\   map to guest = Bad User' /etc/samba/smb.conf
fi

systemctl enable smbd >/dev/null
systemctl restart smbd
echo '    → Samba //<host>/public guest-readable'
""",
    powershell_setup="",
)


_SAMBA_WIN = LiveService(
    id="samba_win",
    name="Windows SMB share (Everyone-readable)",
    summary="An additional SMB share at C:\\Lab\\share with Everyone:Read access.",
    supported_os=(TargetOS.WINDOWS_11,),
    vulnerabilities=(
        Vulnerability(
            name="Everyone-readable SMB share",
            detail="Share 'LabShare' (C:\\Lab\\share) granted Everyone:Read. "
                   "Adds enumerable network surface beyond the template's "
                   "default share.",
            cwe="CWE-284",
        ),
    ),
    bash_setup="",
    powershell_setup=r"""
Write-Host '[+] Adding Windows SMB lab share'
$path = 'C:\Lab\share'
New-Item -ItemType Directory -Force $path | Out-Null
'lab share — read only for Everyone' | Out-File -Encoding ascii "$path\README.txt"

if (Get-SmbShare -Name 'LabShare' -ErrorAction SilentlyContinue) {
    Remove-SmbShare -Name 'LabShare' -Force
}
New-SmbShare -Name 'LabShare' -Path $path -ReadAccess 'Everyone' | Out-Null
Write-Host '    -> \\<host>\LabShare (Everyone:Read)'
""",
)


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

AVAILABLE_SERVICES: tuple[LiveService, ...] = (
    _APACHE,
    _NGINX,
    _MYSQL,
    _FTP_VSFTPD,
    _FTP_IIS,
    _SAMBA,
    _SAMBA_WIN,
)


def get_service(service_id: str) -> LiveService | None:
    for s in AVAILABLE_SERVICES:
        if s.id == service_id:
            return s
    return None