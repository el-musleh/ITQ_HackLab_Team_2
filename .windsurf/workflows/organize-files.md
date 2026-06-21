---
description: Organize new files into the correct project folders (docs, src, notebooks)
---

# Project File Organization Workflow

When creating or moving files in the `ITQ_HackLab_Team_2` project, place them in the correct top-level folder. Keep the repository clean, predictable, and easy to navigate for both humans and AI agents.

## 1. Markdown documentation → `docs/`

All Markdown files belong in `docs/`. Group related files in subdirectories when it makes sense.

- **Root exceptions (never move these)**: `README.md`, `LICENSE`
- **Implementation notes / design decisions**: `docs/<topic>.md` (e.g., `docs/arena-coordinate-fix.md`)
- **Challenge or simulation docs**: `docs/challenge/` or `docs/simulation/`
- **Troubleshooting / quick reference**: `docs/troubleshooting.md`, `docs/quick-reference.md`

## 2. Python source code → `src/`

All `.py` files live under `src/`. Use the existing module structure; create new modules only when a file does not fit an existing one.

- **Modules**: `src/control/`, `src/hardware/`, `src/perception/`, `src/simulation/`, `src/SCSCtrl/`, `src/utils/`
- **Standalone scripts / entry points**: `src/main.py`, `src/navigation.py`, `src/brainrot.py`, etc.
- **Root exception**: `setup.py` stays in the project root for package installation

### Import convention

Always import from `src` explicitly so the project works regardless of how the working directory is set.

```python
# Good
from src.control.state_machine import StateMachine
from src.hardware.camera import Camera

# Avoid
from control.state_machine import StateMachine
```

If a notebook or script must run from the project root, ensure `src/` is on the Python path or use the absolute import style above.

## 3. Jupyter notebooks → `notebooks/`

All `.ipynb` files belong in `notebooks/`. Preserve existing subfolder structure.

- **Feature notebooks**: `notebooks/basic_motion/`, `notebooks/collison_aviodance/`, `notebooks/jetank/`, `notebooks/road_following/`, `notebooks/object_following/`, `notebooks/teleoperations/`
- **Miscellaneous one-off notebooks**: `notebooks/misc/`
- **Root exception**: none — move every notebook into `notebooks/`

## 4. Configuration and automation → project root

Keep these files in the project root:

- `setup.py`
- `config.yaml`
- `pytest.ini`
- `config.sh`
- `install.sh`
- `setup.sh`
- `.gitignore`

## 5. Checklist before finishing

After adding or moving files, verify:

- [ ] No `.md` files are in the root except `README.md` and `LICENSE`
- [ ] No `.py` files are in the root except `setup.py`
- [ ] No `.ipynb` files are outside `notebooks/`
- [ ] All Python imports use the `src.<module>.<file>` prefix
- [ ] `pytest` still passes or imports resolve correctly
- [ ] Any hardcoded paths in moved notebooks/scripts are updated

## 6. Common examples

| File type | Bad location | Good location |
|-----------|--------------|---------------|
| New feature doc | `NEW-FEATURE.md` | `docs/new-feature.md` |
| New detector module | `perception/new_detector.py` | `src/perception/new_detector.py` |
| New demo notebook | `new_demo.ipynb` | `notebooks/misc/new_demo.ipynb` |
| Utility script | `utils.py` | `src/utils/utils.py` |

## 7. When in doubt

If a file does not fit cleanly into one of the categories above, place it in the closest logical folder and leave a note in the PR or commit message explaining the exception. Prefer moving an existing file over duplicating logic.
