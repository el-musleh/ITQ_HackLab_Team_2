import json

def patch_basic_motion():
    path = "/workspace/itq-bottle-cap-collector/basic_motion/basic_motion.ipynb"
    print(f"Patching {path}...")
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)
        
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        source_str = "".join(source) if isinstance(source, list) else source
        
        if "middle_box = widgets.HBox([left_button, stop_button, right_button]" in source_str:
            print("Found target cell.")
            if "stop_button =" not in source_str:
                # Add stop_button creation
                lines = source_str.splitlines()
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if "right_button =" in line:
                        # Append the definition of stop_button right after right_button is defined
                        new_lines.append("stop_button = widgets.Button(description='stop', layout=button_layout)")
                cell["source"] = [l + "\n" for l in new_lines]
                print("stop_button definition added.")
                break
                
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Patching complete.")

if __name__ == "__main__":
    patch_basic_motion()
