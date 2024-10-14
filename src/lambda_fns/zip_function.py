import os
import shutil
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

    # Create zip file
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    zip_path = os.path.join(output_dir, f'{function_name}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(function_dir):
            for file in files:
                if file != 'requirements.txt':  # Skip requirements.txt
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, function_dir)
                    zipf.write(file_path, arcname)
    
    print(f"Function '{function_name}' code zipped successfully to {zip_path}")

if __name__ == "__main__":
    zip_lambda_function()