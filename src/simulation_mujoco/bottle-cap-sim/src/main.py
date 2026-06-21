"""Entry point: build scene and run the autonomous simulation.

Usage:
    python -m src.main
"""

import os
import sys


def _ensure_mjpython() -> None:
    """On macOS, MuJoCo's passive viewer requires the mjpython trampoline.

    We set PYGLFW_LIBRARY so the bundled libglfw.3.dylib is found reliably
    inside the mjpython native binary context, and _MJPY_GUARD to stop the
    loop (sys.executable is not 'mjpython' even when running inside it).
    """
    if sys.platform != "darwin":
        return
    if os.environ.get("_MJPY_GUARD") == "1":
        return  # already running under mjpython — don't re-exec

    import shutil

    mjpython = shutil.which("mjpython")
    if mjpython is None:
        import mujoco as _mj
        mjpython = os.path.join(os.path.dirname(_mj.__file__), "mjpython")
    if not os.path.isfile(mjpython):
        raise RuntimeError(
            "mjpython not found. Install mujoco via pip, then run:\n"
            "    mjpython -m src.main"
        )

    # Point glfw at the bundled native library so it loads under mjpython.
    try:
        import glfw as _glfw_pkg
        glfw_lib = os.path.join(
            os.path.dirname(_glfw_pkg.__file__), "libglfw.3.dylib"
        )
        if os.path.isfile(glfw_lib):
            os.environ["PYGLFW_LIBRARY"] = glfw_lib
    except ImportError:
        pass

    # Preserve sys.path so 'src.*' imports resolve inside the mjpython process.
    import pathlib
    project_root = str(pathlib.Path(__file__).parent.parent)
    pp = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = (project_root + (":" + pp if pp else ""))

    os.environ["_MJPY_GUARD"] = "1"
    # Pass -m src.main so Python resolves the package correctly (not as a raw script).
    os.execv(mjpython, [mjpython, "-m", "src.main"])


def main() -> None:
    _ensure_mjpython()

    from src.scene_builder import build_scene
    from src.viewer import run_sim

    xml, cap_colors = build_scene()
    run_sim(xml, cap_colors)


if __name__ == "__main__":
    main()
