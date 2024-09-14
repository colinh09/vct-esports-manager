import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

def zip_lambda_function():
    # Paths
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tools_dir)
    
    # Prompt user for function name
    function_name = input("Enter the name of the function directory to zip: ").strip()
    function_dir = os.path.join(tools_dir, function_name)
    output_dir = os.path.join(project_root, 'lambda_fns/zipped_fns')
    
    if not os.path.exists(function_dir):
        print(f"Function directory '{function_name}' not found.")
        return

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy function code to temp directory
        shutil.copytree(function_dir, os.path.join(tmpdir, function_name))
        
        # Install dependencies
        requirements_file = os.path.join(function_dir, 'requirements.txt')
        if os.path.exists(requirements_file):
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install',
                '-r', requirements_file,
                '-t', os.path.join(tmpdir, function_name)
            ])
        
        # Create zip file
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        zip_path = os.path.join(output_dir, f'{function_name}.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(os.path.join(tmpdir, function_name)):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.join(tmpdir, function_name))
                    zipf.write(file_path, arcname)
    
    print(f"Function '{function_name}' zipped successfully to {zip_path}")

if __name__ == "__main__":
    zip_lambda_function()