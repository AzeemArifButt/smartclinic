"""
Run this from the backend folder:
  cd d:\Backup\SmartClinic\backend
  python ..\start_with_ngrok.py
"""
import subprocess
import sys
import time
import os

os.chdir(os.path.join(os.path.dirname(__file__), "backend"))

from pyngrok import ngrok

# Start ngrok tunnel
tunnel = ngrok.connect(8000)
public_url = tunnel.public_url
if public_url.startswith("http://"):
    public_url = public_url.replace("http://", "https://")

print("\n" + "="*60)
print("NGROK PUBLIC URL:")
print(f"  {public_url}")
print()
print("SET THIS AS YOUR META WEBHOOK URL:")
print(f"  {public_url}/api/whatsapp/webhook")
print()
print("VERIFY TOKEN: smartclinic2024")
print("="*60 + "\n")

# Start uvicorn
subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"])
