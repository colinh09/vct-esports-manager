import requests
import gzip
import shutil
import os
from io import BytesIO

# Base URL for the S3 bucket
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

def download_gzip_and_write_to_xml(file_name, full_url):
    if os.path.isfile(f"{file_name}.xml"):
        print(f"{file_name}.xml already exists, skipping download.")
        return

    response = requests.get(full_url)
    if response.status_code == 200:
        try:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                with open(f"{file_name}.xml", 'wb') as output_file:
                    shutil.copyfileobj(gzipped_file, output_file)
                print(f"{file_name}.xml written")
        except Exception as e:
            print("Error:", e)
    else:
        print(response)
        print(f"Failed to download {file_name}")

def download_fandom_xml_files():
    directory = "../data/fandom"
    if not os.path.exists(directory):
        os.makedirs(directory)

    fandom_files = ["valorant_esports_pages", "valorant_pages"]

    for file_name in fandom_files:
        file_path = f"{directory}/{file_name}"
        full_url = f"{S3_BUCKET_URL}/fandom/{file_name}.xml.gz"
        download_gzip_and_write_to_xml(file_path, full_url)

if __name__ == "__main__":
    download_fandom_xml_files()