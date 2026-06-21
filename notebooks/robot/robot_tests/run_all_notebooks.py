import glob
import os
import subprocess
import json
import sys
import io

# Configure stdout and stderr to use UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_notebook(notebook_path):
    print(f"\n==================================================")
    print(f"RUNNING: {notebook_path}")
    print(f"==================================================")
    sys.stdout.flush()
    
    cmd = [
        "jupyter", "nbconvert", 
        "--to", "notebook", 
        "--execute", 
        "--stdout",
        notebook_path
    ]
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    stdout_bytes, stderr_bytes = process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    
    if process.returncode == 0:
        print(f"SUCCESS: {notebook_path}")
        sys.stdout.flush()
        return True, ""
    else:
        print(f"FAILED: {notebook_path}")
        print("--- Execution Error Details ---")
        print(stderr)
        sys.stdout.flush()
        return False, stderr

def main():
    notebooks = []
    for root, dirs, files in os.walk("."):
        # Ignore checkpoints, virtual environments, build/dist and external libraries
        if any(x in root for x in ["venv", ".ipynb_checkpoints", "build", "dist", "SCSCtrl"]):
            continue
        for f in files:
            if f.endswith(".ipynb"):
                notebooks.append(os.path.join(root, f))
                
    notebooks = sorted(list(set(notebooks)))
    print(f"Found {len(notebooks)} notebooks to test:")
    for nb in notebooks:
        print(f"  - {nb}")
    sys.stdout.flush()
        
    results = {}
    failed = []
    for nb in notebooks:
        success, err = run_notebook(nb)
        results[nb] = success
        if not success:
            failed.append((nb, err))
            
    print(f"\n==================================================")
    print(f"SUMMARY OF NOTEBOOK RUNS")
    print(f"==================================================")
    for nb, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"{nb}: {status}")
    sys.stdout.flush()
        
    if failed:
        print(f"\nThere are {len(failed)} failed notebooks:")
        for nb, _ in failed:
            print(f"  - {nb}")
        sys.stdout.flush()
        sys.exit(1)
    else:
        print("\nAll notebooks ran successfully!")
        sys.stdout.flush()
        sys.exit(0)

if __name__ == "__main__":
    main()
