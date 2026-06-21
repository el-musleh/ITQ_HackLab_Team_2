import json
import os
import re

# Auto-detect project root by searching for config.yaml marker
project_root = os.getcwd()
while not os.path.exists(os.path.join(project_root, 'config.yaml')) and project_root != '/':
    project_root = os.path.dirname(project_root)

def clean_user_content(content):
    if not content:
        return ""
    # Extract content within <USER_REQUEST> tags if present
    match = re.search(r'<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>', content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return content.strip()

def export_transcript():
    log_path = "/root/.gemini/antigravity-cli/brain/103c705c-dcdf-4af1-b9e5-29f68718db32/.system_generated/logs/transcript_full.jsonl"
    dest_path = os.path.join(project_root, "docs", "conversation_transcript.md")
    
    print(f"Reading logs from {log_path}...")
    if not os.path.exists(log_path):
        print("Error: Logs file does not exist!")
        return
        
    steps = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                steps.append(json.loads(line))
            except Exception as e:
                print("Failed to parse log line:", e)
                
    print(f"Parsed {len(steps)} log steps.")
    
    markdown_content = []
    markdown_content.append("# Antigravity Conversation Transcript\n")
    markdown_content.append(f"- **Conversation ID:** `103c705c-dcdf-4af1-b9e5-29f68718db32`\n")
    markdown_content.append(f"- **Exported On:** 2026-06-20\n")
    markdown_content.append("\n---\n\n")
    
    for step in steps:
        source = step.get("source")
        step_type = step.get("type")
        content = step.get("content", "")
        created_at = step.get("created_at", "")
        
        # Format time for display (e.g. 15:30:12)
        time_str = ""
        if created_at:
            time_parts = created_at.split("T")
            if len(time_parts) > 1:
                time_str = f" @ {time_parts[1].rstrip('Z')}"
                
        if step_type == "USER_INPUT":
            cleaned_req = clean_user_content(content)
            markdown_content.append(f"### 👤 User{time_str}\n\n")
            markdown_content.append(f"> {cleaned_req}\n\n")
            markdown_content.append("---\n\n")
            
        elif step_type == "PLANNER_RESPONSE":
            tool_calls = step.get("tool_calls", [])
            
            # Print the assistant response if there is content
            if content:
                markdown_content.append(f"### 🤖 Antigravity Assistant{time_str}\n\n")
                markdown_content.append(f"{content}\n\n")
                
            # If tool calls are present, add a summary block
            if tool_calls:
                # If we hadn't already printed the header
                if not content:
                    markdown_content.append(f"### 🤖 Antigravity Assistant{time_str}\n\n")
                
                markdown_content.append("#### 🛠️ Executed Tools\n")
                for tc in tool_calls:
                    tc_name = tc.get("name")
                    tc_args = tc.get("args", {})
                    summary = tc_args.get("toolSummary", tc_args.get("CommandLine", ""))
                    markdown_content.append(f"- **{tc_name}**: *{summary}*\n")
                markdown_content.append("\n")
                
            if content or tool_calls:
                markdown_content.append("---\n\n")
                
        elif step_type == "CHECKPOINT":
            # Resuming summary or system state checkpoints
            pass
            
    # Write to doc folder
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.writelines(markdown_content)
        
    print(f"Conversation exported successfully to {dest_path}")

if __name__ == "__main__":
    export_transcript()
