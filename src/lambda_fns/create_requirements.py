import os
import subprocess
import sys

def install_pipreqs():
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pipreqs'])
    except subprocess.CalledProcessError:
        print("Failed to install pipreqs. Please install it manually.")
        sys.exit(1)

def generate_requirements():
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Prompt user for function name
    function_name = input("Enter the name of the function directory: ").strip()
    function_dir = os.path.join(tools_dir, function_name)
    
    if not os.path.exists(function_dir):
        print(f"Function directory '{function_name}' not found.")
        return

    try:
        # Generate requirements.txt
        subprocess.check_call(['pipreqs', function_dir, '--force'])
        print(f"Generated requirements.txt for '{function_name}'")
        
        # Read and print the contents of requirements.txt
        req_file = os.path.join(function_dir, 'requirements.txt')
        with open(req_file, 'r') as f:
            print("\nContents of requirements.txt:")
            print(f.read())
    except subprocess.CalledProcessError:
        print(f"Failed to generate requirements for '{function_name}'")

if __name__ == "__main__":
    install_pipreqs()
    generate_requirements()