# Troubleshooting — Known Issues & Fixes

## Issue: SSH Fails (`Permission denied`)

**Cause:** The Jetson runs in a Docker container. No `sshd`, no `systemd`, no `sudo`.

**Fix:** Don't use SSH. Use Jupyter Lab terminal instead.

```
http://192.168.0.100:8888/lab → File → New → Terminal
```

---

## Issue: `sudo: command not found`

**Cause:** Docker container runs as root. `sudo` is unnecessary and not installed.

**Fix:** Run commands without `sudo`.
```bash
# Wrong:
sudo apt-get install python3-pip

# Right:
apt-get install python3-pip
```

---

## Issue: `systemctl` Fails

**Cause:** Docker containers don't use `systemd` as init system.

**Fix:** Don't use `systemctl`. Services are managed by the host or already running.

```bash
# This fails:
systemctl status ssh

# This is fine — Jupyter is already running as a service on the host
```

---

## Issue: `setup.sh` Says "Not Jetson"

**Cause:** The script checks `/etc/nv_tegra_release` which doesn't exist inside the Docker container.

**Fix:** Run setup manually (see `04-setup.md`). The container already has OpenCV and jetbot.

---

## Issue: Camera Initialization Fails

**Cause:** Camera was not properly released by a previous kernel session.

**Fix:** Restart the Jupyter kernel.

```
Right-click notebook tab → Shut Down Kernel → Close tab → Reopen notebook
```

---

## Issue: Servo `Permission Denied` on `/dev/ttyTHS1`

**Cause:** Serial port permissions not set.

**Fix:** In Jupyter Terminal:
```bash
chmod 777 /dev/ttyTHS1
```

---

## Issue: `git push` Asks for Password (and fails)

**Cause:** GitHub no longer accepts account passwords for git operations.

**Fix:** Use a **Personal Access Token** as the password.

1. Generate at: https://github.com/settings/tokens
2. Select `repo` scope
3. Use token instead of password when pushing

---

## Issue: Jupyter Notebook Tab Crashes / Freezes

**Cause:** Jetson Nano has only 4GB RAM. OpenCV frames leak memory.

**Fix:**
- Restart kernel often (`Kernel → Restart`)
- Lower camera resolution: `Camera.instance(width=320, height=240)`
- Close other notebooks and browser tabs
- Run only one notebook at a time
- Add `cv2.destroyAllWindows()` between cells

---

## Issue: No Internet on Jetson

**Check:**
```bash
curl -I https://github.com
```

**If fails:** Use Jupyter Upload/Download instead of git.
- Upload: Jupyter Lab → Right-click → Upload
- Download: Jupyter Lab → Right-click file → Download

---

## Issue: `.gitignore` Not Working (venv/ still shows in `git status`)

**Fix:**
```bash
git rm -r --cached venv/
git add .gitignore
git commit -m "fix: ignore venv"
```

---

## Issue: Color Tracking Detects Wrong Object

**Cause:** HSV thresholds too wide.

**Fix:** Narrow the HSV range:
```python
# Use JETANK_4_colorRecognition notebook to calibrate
# Or adjust manually:
colorLower = np.array([H_min, S_min, V_min])
colorUpper = np.array([H_max, S_max, V_max])
```

---

## Quick Diagnostic Checklist

```bash
# 1. Network
ping -c 3 192.168.0.100          # laptop → Jetson
curl -I https://github.com        # Jetson → internet

# 2. Camera
python3 -c "from jetbot import Camera; c = Camera.instance(); print('OK')"

# 3. Servos
python3 -c "from SCSCtrl import TTLServo; TTLServo.servoAngleCtrl(1, 0, 1, 150); print('OK')"

# 4. Git
git status                          # check what's changed
git log --oneline -3               # last commits

# 5. Memory
free -h                           # RAM usage
```
