import os
import json

def load_metadata(metadata_path):
    """Load metadata from specified JSON file"""
    with open(metadata_path, "r") as file:
        return json.load(file)

def create_output_directory(output_path):
    """Create directory structure if it doesn't exist"""
    os.makedirs(output_path, exist_ok=True)
    return output_path

def generate_git_command(project_dir, project_name, base_commit, src_path, dest_path):
    """Generate git checkout and copy command string"""
    return (
        f"cd {os.path.join(project_dir, project_name)} && "
        f"git checkout {base_commit} && "
        f"cp {src_path} {dest_path}"
    )

def execute_command(cmd, instance_id, path):
    """Execute system command and handle errors"""
    print(cmd)
    status = os.system(cmd)
    if status != 0:
        print(f"ERROR in {instance_id}: {path} !!!")
    return status

def process_buggy_files(instance_data, project_dir, metadata_entry, output_base):
    """Process and copy buggy files for a single metadata entry"""
    instance_id = metadata_entry["instance_id"]
    project_name = "-".join(instance_id.split("-")[:-1])
    base_commit = metadata_entry["base_commit"]
    
    if instance_id not in instance_data:
        return
    
    # Prepare output directories
    output_dir = os.path.join(output_base, "techniques", instance_id)
    buggy_files_dir = create_output_directory(os.path.join(output_dir, "buggy_files"))
    
    # Process each file path
    for path in instance_data[instance_id].keys():
        sanitized_path = path.replace("/", "__")
        dest_path = os.path.abspath(os.path.join(buggy_files_dir, sanitized_path))
        
        if os.path.exists(dest_path):
            continue
            
        cmd = generate_git_command(
            project_dir, 
            project_name,
            base_commit,
            path,
            dest_path
        )
        execute_command(cmd, instance_id, path)

def process_exp_files(exp_dir, metadata, project_dir):
    """Process all experiment files in the experiment directory"""
    for filename in os.listdir(exp_dir):
        if not filename.endswith(".json"):
            continue
            
        exp_id = filename[:-5]
        file_path = os.path.join(exp_dir, filename)
        
        with open(file_path, "r") as file:
            exp_data = json.load(file)
            
        for metadata_entry in metadata:
            process_buggy_files(
                exp_data,
                project_dir,
                metadata_entry,
                "./data"  # Base output directory
            )

def main():
    """Main entry point of the program"""
    # Configuration parameters
    PROJECTS_DIR = "../swe_projects/"
    METADATA_PATH = "../swe_bench_verified.json"
    EXP_DIR = "./exp_buggy_line_info/"
    
    # Load metadata
    metadata = load_metadata(METADATA_PATH)
    
    # Process all experiment files
    process_exp_files(EXP_DIR, metadata, PROJECTS_DIR)

if __name__ == "__main__":
    main()