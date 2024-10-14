import os
import subprocess
import zipfile
import sys
import shutil

def create_lambda_layer():
    # Prompt user for requirements file path
    requirements_file = input("Enter the path to your requirements.txt file: ").strip()

    # Ensure the requirements file exists
    if not os.path.exists(requirements_file):
        print(f"Requirements file '{requirements_file}' not found.")
        return

    # Prompt user for output zip file name
    output_zip = input("Enter the name for the output zip file (default: lambda_layer.zip): ").strip()
    if not output_zip:
        output_zip = "lambda_layer.zip"
    if not output_zip.endswith('.zip'):
        output_zip += '.zip'

    # Create the simplified directory structure for the layer
    temp_dir = os.path.join(os.getcwd(), "temp_layer")
    layer_dir = os.path.join(temp_dir, "python")
    os.makedirs(layer_dir, exist_ok=True)

    try:
        # Install dependencies
        print("Installing dependencies...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", requirements_file,
            "-t", layer_dir
        ])

        # Create zip file
        print(f"Creating zip file: {output_zip}")
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)

        print(f"Lambda layer created successfully: {output_zip}")

    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    create_lambda_layer()