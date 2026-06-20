import json
import os
import re

def patch_notebook_loops(path):
    with open(path, "r", encoding="utf-8") as f:
        try:
            nb = json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return False
            
    modified = False
    
    # We look for patterns like:
    # while True:
    # while(True):
    # while 1:
    # while(1):
    # with optional spacing/tabs
    pattern = re.compile(r'^(\s*)while\s*(?:True|\(True\)|1|\(1\))\s*:', re.MULTILINE)
    
    for idx, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        
        source = cell.get("source", [])
        # source can be a list of strings or a single string
        source_str = "".join(source) if isinstance(source, list) else source
        
        if pattern.search(source_str):
            print(f"Found infinite loop in {path} at cell {idx}:")
            # Print the lines containing while True
            for line in source_str.splitlines():
                if "while" in line and ("True" in line or "1" in line):
                    print(f"  > {line}")
            
            # Replace the pattern with a capped range
            # We preserve the indentation of the line!
            def repl(match):
                indent = match.group(1)
                return f"{indent}for _ in range(5):  # patched infinite loop"
                
            new_source_str = pattern.sub(repl, source_str)
            
            # Save back to cell
            # nbconvert handles both list of strings or single string, but list of strings is standard
            cell["source"] = [line + "\n" for line in new_source_str.splitlines()]
            # strip trailing newline for the last line if the original did not have it
            if new_source_str and not new_source_str.endswith("\n") and cell["source"]:
                cell["source"][-1] = cell["source"][-1].rstrip("\n")
                
            modified = True
            
    if modified:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
        print(f"Patched {path}")
        return True
    return False

def main():
    print("Scanning all notebooks for infinite loops...")
    count = 0
    for root, dirs, files in os.walk("."):
        if any(x in root for x in ["venv", ".ipynb_checkpoints", "build", "dist"]):
            continue
        for file in files:
            if file.endswith(".ipynb"):
                path = os.path.join(root, file)
                if patch_notebook_loops(path):
                    count += 1
    print(f"Finished. Patched loops in {count} notebooks.")

if __name__ == "__main__":
    main()
