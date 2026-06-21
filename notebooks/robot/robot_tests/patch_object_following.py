import json
import os

# Auto-detect project root by searching for config.yaml marker
project_root = os.getcwd()
while not os.path.exists(os.path.join(project_root, 'config.yaml')) and project_root != '/':
    project_root = os.path.dirname(project_root)

def patch_object_following():
    path = os.path.join(project_root, "object_following", "live_demo.ipynb")
    print(f"Patching {path}...")
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)
        
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        source_str = "".join(source) if isinstance(source, list) else source
        
        if "detections = model(camera.value)" in source_str:
            print("Found target cell.")
            if "ObjectDetector" not in source_str:
                # Add import and definition of model at the start of this cell
                new_source = [
                    "from jetbot import ObjectDetector\n",
                    "model = ObjectDetector('ssd_mobilenet_v2_coco.engine')\n",
                    "detections = model(camera.value)\n",
                    "\n",
                    "print(detections)"
                ]
                cell["source"] = new_source
                print("Added ObjectDetector and model definition to cell.")
                break
                
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Patching complete.")

if __name__ == "__main__":
    patch_object_following()
