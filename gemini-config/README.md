# Gemini CLI (agy) + Antigravity Permission Config

Copy of the Gemini CLI and Antigravity configurations that grant the AI agents broad command execution permissions — matching the setup on this host OS.

## Files

### Gemini CLI

| File | Destination | Purpose |
|------|-------------|---------|
| `settings.json` | `~/.gemini/settings.json` | Enables permanent tool approval, auto-add to policy, YOLO mode, and sandbox network access |
| `auto-saved.toml` | `~/.gemini/policies/auto-saved.toml` | **The key file**: a `priority = 999` catch-all rule allows `run_shell_command` for **any** command without prompting |
| `trustedFolders.json` | `~/.gemini/trustedFolders.json` | Marks the home directory as a trusted workspace |

### Antigravity

| File | Destination | Purpose |
|------|-------------|---------|
| `antigravity-settings.json` | `~/.gemini/antigravity/settings.json` | Same as above but for Antigravity IDE |
| `antigravity-auto-saved.toml` | `~/.gemini/antigravity/policies/auto-saved.toml` | Same broad-allow policy for Antigravity |

## How it works

### The wildcard: `command(*)` equivalent

In **Claude Code** you write `Bash(*)` to allow any shell command. In Gemini/Antigravity CLI, the wildcard is the **absence of a `commandPrefix`**. A rule like this with no restriction means *all* commands are allowed:

```toml
[[rule]]
decision = "allow"
priority = 999
toolName = "run_shell_command"
# No commandPrefix = ANY command is allowed
```

The `auto-saved.toml` policy uses two priority levels:

- **Priority 999** — broad *allow* rules with no `commandPrefix` restriction. This means the agent can execute any shell command, write any file, etc. without asking.
- **Priority 950** — narrow *deny* rules that block only destructive commands (`reboot`, `poweroff`, `shutdown`, `rm -rf`, `git push`).

This is the same "broad allow, narrow deny" model used by Claude Code on this machine.

## Usage

### Install locally (host)

```bash
bash gemini-config/deploy.sh
```

### Install in a Docker container

```bash
# Copy the whole folder into the container
docker cp gemini-config <container>:/tmp/gemini-config

# Then inside the container
bash /tmp/gemini-config/deploy.sh
```

Or bake it into a `Dockerfile`:

```dockerfile
COPY gemini-config /tmp/gemini-config
RUN bash /tmp/gemini-config/deploy.sh
```

## After installing

Restart any running `agy` sessions for the new policy to take effect.

## Jupyter notebook integration

The Jupyter kernel has also been updated (`kernel.json` → `kernel_launcher.sh`) so that notebooks run with the full shell environment (including `~/.local/bin` where `agy` lives). Restart Jupyter kernels after deployment.
