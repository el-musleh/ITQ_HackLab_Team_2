import json
import os

# Auto-detect project root by searching for config.yaml marker
project_root = os.getcwd()
while not os.path.exists(os.path.join(project_root, 'config.yaml')) and project_root != '/':
    project_root = os.path.dirname(project_root)

def patch_use_model():
    path = os.path.join(project_root, "use_model.ipynb")
    print(f"Patching {path}...")
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)
        
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        source_str = "".join(source) if isinstance(source, list) else source
        
        if "camera = Camera.instance(width=224, height=224)" in source_str:
            print("Found target camera init cell in use_model.ipynb.")
            
            new_source = [
                "CONFIDENCE_THRESHOLD = 0.8\n",
                "\n",
                "try:\n",
                "    camera = Camera.instance(width=224, height=224) \n",
                "    if type(camera).__name__ in ['MockCamera', 'DummyCamera']:\n",
                "        print('Real camera failed to initialize. Fell back to Mock/Dummy camera.')\n",
                "    else:\n",
                "        print('Real camera initialized successfully.')\n",
                "except Exception as e:\n",
                "    print(f'Could not initialize real camera: {e}')\n",
                "    print('Falling back to MockCamera...')\n",
                "    try:\n",
                "        from tests.mock_camera import MockCamera\n",
                "        camera = MockCamera.instance(width=224, height=224)\n",
                "        print('MockCamera initialized successfully.')\n",
                "    except Exception as e2:\n",
                "        print(f'Failed to load MockCamera: {e2}. Creating dummy camera...')\n",
                "        import numpy as np\n",
                "        class DummyCamera:\n",
                "            def __init__(self):\n",
                "                self.value = np.zeros((224, 224, 3), dtype=np.uint8)\n",
                "            def observe(self, *args, **kwargs): pass\n",
                "            def unobserve_all(self, *args, **kwargs): pass\n",
                "            def stop(self, *args, **kwargs): pass\n",
                "        camera = DummyCamera()\n",
                "        print('DummyCamera initialized successfully.')\n",
                "\n",
                "livefeed = ipywidgets.widgets.Image() \n",
                "camera_link = traitlets.dlink((camera, 'value'), (livefeed, 'value'), transform=bgr8_to_jpeg)\n",
                "snapshot_widget = ipywidgets.widgets.Image(width=camera.width, height=camera.height)\n",
                "\n",
                "def take_snapshot():\n",
                "    pass\n",
                "\n",
                "# Display the camera widgets so they are visible in the notebook output\n",
                "display(ipywidgets.widgets.HBox([livefeed, snapshot_widget]))\n"
            ]
            cell["source"] = new_source
            print("Successfully updated cell source and added display widgets.")
            break
            
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Patching complete.")

if __name__ == "__main__":
    patch_use_model()
