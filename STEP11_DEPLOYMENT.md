# Step 11 — Deployment & One-Click Launch

## Windows

Double-click `scripts/start.bat` to start the application. The launcher validates Docker/Compose and required files, starts the stack, waits for backend and frontend health, discovers the dynamically assigned frontend port, and opens the application.

Optional PowerShell forms:

```powershell
.\scripts\start.ps1
.\scripts\start.ps1 -NoBrowser
.\scripts\start.ps1 -Rebuild
.\scripts\start.ps1 -Rebuild -NoBrowser
```

## Linux/macOS

```sh
./scripts/start.sh
./scripts/start.sh --no-browser
./scripts/start.sh --rebuild
./scripts/start.sh --rebuild --no-browser
```

## Stop / status

Windows:

```powershell
.\scripts\status.ps1
.\scripts\stop.ps1
```

Linux/macOS:

```sh
./scripts/status.sh
./scripts/stop.sh
```

## Deployment behavior

- Host ports are Docker-assigned (`published: "0"`) and bound to loopback.
- The frontend is same-origin and proxies API traffic to the backend container.
- The launcher never assumes a fixed host port.
- The launcher is repository-relative; the package can be moved to another folder.
- Startup is repeat-safe through `docker compose up -d`.
- `--rebuild` forces a fresh image build before startup.
- The launcher waits for both services to report `healthy` before showing the URL.
- Required package files are checked before startup.
- No host Python, Node.js, MySQL, MongoDB, or ClickHouse installation is required for the Docker deployment.
