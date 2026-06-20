# Git Workflow — From Jetson & Laptop

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable, team-shared code |
| `develop` | Active integration branch |
| `kais-navigation` | Navigation module (feature) |
| `feature/<name>` | Each teammate's module branch |

## Laptop Workflow (All Team Members)

```bash
cd itq-bottle-cap-collector

# Create feature branch
git checkout -b feature/<your-module>

# Code, then commit
git add .
git commit -m "feat: add PID controller"

# Push
git push origin feature/<your-module>
```

## Jetson Workflow (Operator)

```bash
cd /workspace/itq-bottle-cap-collector

# Set config (one-time)
git config user.name "Mohammad El Musleh"
git config user.email "your-email@example.com"

# Pull latest
git pull origin main

# Run tests, report results
```

## Pushing from Jetson (Personal Access Token Required)

GitHub dropped password auth. Use a **Personal Access Token**.

### Generate Token (on laptop browser)

1. Go to: https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select `repo` scope
4. **Copy the token** (looks like `ghp_xxxxxxxxxxxx`)

### Push from Jetson

```bash
git push origin $(git branch --show-current)
```

When prompted for password, **paste the token** (not your GitHub password).

### Store Token Permanently

```bash
git config credential.helper store
git push origin $(git branch --show-current)
# Paste token once — saved for future pushes
```

Token stored in `~/.git-credentials` (plain text). **Delete after hackathon:**
```bash
rm ~/.git-credentials
```

## Merging to Main

1. Go to: `https://github.com/el-musleh/ITQ_HackLab_Team_2`
2. Click **Pull requests** → **New pull request**
3. `base: main` ← `compare: feature/<your-branch>`
4. **Create pull request** → **Merge pull request**

Team members then pull:
```bash
git pull origin main
```

## Useful Git Commands

```bash
# Check what changed
git status
git diff <filename>

# Discard changes in a file
git restore <filename>

# Unstage a file
git restore --staged <filename>

# Reset to last commit (dangerous)
git reset --hard HEAD

# See commit history
git log --oneline -5
```
