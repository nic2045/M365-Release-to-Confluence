# Script-Libary — Claude Instructions

@../CLAUDE.md
## Dokumentation aktuell halten

Bei jeder Änderung an der Sammlung gilt:

- **Neues Script**: Comment-Based Help am Anfang eintragen (`.SYNOPSIS`, `.DESCRIPTION`, `.EXAMPLE`, `.NOTES` mit Bereich und Voraussetzungen). Vorlage: [CountMigration.ps1](Scripts/Exchange/Online/Migration/CountMigration.ps1)
- **Neue Modul-Funktion**: Comment-Based Help in die `.ps1`-Datei unter `Modules/NDTools/Public/`. Vorlage: [Connect-MSCloudConnections.ps1](Modules/NDTools/Public/Core/Connect-MSCloudConnections.ps1)
- **Neuer Ordner in `Scripts/`**: Struktur-Abschnitt in [README.md](README.md) ergänzen
- **Modul veröffentlicht**: `ReleaseNotes` in [NDTools.psd1](Modules/NDTools/NDTools.psd1) aktualisieren

## Repo-Struktur

```
Modules/NDTools/   PowerShell-Modul (gemeinsame Cmdlets)
Build/                Publish-Script für GitHub Packages
Scripts/
  Azure/              Azure Backup-Scripts
  Endpoint/           Scripts die auf dem Windows-Client ausgeführt werden
  EntraID/            CA-Policies, Groups, Licenses, Users
  Exchange/OnPrem/    Exchange 2016
  Exchange/Online/    Exchange Online + Migration/
  Intune/             Compliance-Reports
  KI/                 KI-Tools
  Teams/              Microsoft Teams
_Archiv/              Veraltete Dateien und Export-Reports
```

## Modul-Verteilung

Modul wird über GitHub Packages (`nic2045`) verteilt.
Publish: `.\Build\Publish-NDTools.ps1 -Token "ghp_TOKEN"`
Install: `Install-Module NDTools -Repository GitHubPackages -Credential $cred`
