# Network & Connection Guide

## WiFi Details

| | |
|---|---|
| **SSID** | `TP-LINK_744C` |
| **Password** | `15253354` |
| **Jetson IP** | `192.168.0.100` |
| **Jupyter Port** | `8888` |
| **Jupyter Password** | `CIC@Tics1XAI` |

> Your laptop must connect to `TP-LINK_744C` to reach the robot.

## How to Connect (No SSH Needed)

The Jetson runs inside a **Docker container** on the Jetson Nano host. SSH does not work because:
- The container has no `sshd` installed
- The container does not use `systemd`
- `sudo` command is not available

**The correct workflow is Jupyter Lab:**

1. Connect laptop to WiFi `TP-LINK_744C`
2. Open browser: `http://192.168.0.100:8888/lab`
3. Enter password: `CIC@Tics1XAI`
4. Open a Terminal inside Jupyter: `File` → `New` → `Terminal`

## Jupyter Terminal IS the Jetson Shell

Everything runs from the Jupyter Terminal:

```bash
whoami
# output: root

# You are root in the Docker container
# All robot code runs here
```

## File Sync Options

Since SSH is unavailable, use these methods:

### Git (Internet Required)
The Jetson container HAS internet. Use git push/pull.

```bash
# On Jetson (Jupyter Terminal)
cd /workspace/itq-bottle-cap-collector
git pull origin main
```

### Jupyter Upload (No Internet Backup)
```
Jupyter Lab → Right-click folder → Upload → Select file from laptop
```

### Jupyter Download (Get logs/data from Jetson)
```
Jupyter Lab → Right-click file → Download
```

## Verified Network Test

```bash
curl -I https://github.com
# Returns: HTTP/2 200
# Confirms: Internet works from Jetson container
```

```bash
ping -c 3 192.168.0.100
# From laptop: confirms laptop can reach Jetson
```
