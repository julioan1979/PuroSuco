#!/usr/bin/env python3
"""Teste simples de upload para Cloudinary"""

import os
import tempfile
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

print(f"Cloud Name: {os.getenv('CLOUDINARY_CLOUD_NAME')}")
print(f"API Key: {os.getenv('CLOUDINARY_API_KEY')}")

# Create test file
test_content = b"%PDF-1.4\nTeste de PDF"

with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
    tmp_file.write(test_content)
    tmp_path = tmp_file.name

try:
    print(f"\n📤 Uploading test PDF from {tmp_path}...")
    result = cloudinary.uploader.upload(
        tmp_path,
        resource_type="raw",
        public_id=f"purosuco/test/test_pdf",
        overwrite=True,
        timeout=60
    )
    print(f"✅ Success! URL: {result['secure_url']}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    os.unlink(tmp_path)
