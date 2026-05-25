"""
Environment setup helper script.
"""

import subprocess
import sys
from pathlib import Path
import shutil


def main():
    print("🔧 Setting up Virtual Try-On MVP environment...")

    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
        print(f"   Current version: {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(1)

    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")

    # Check if already in venv
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if not in_venv:
        # Create virtual environment
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"])

        # Get pip path
        if sys.platform == "win32":
            pip_path = "venv\\Scripts\\pip"
            python_path = "venv\\Scripts\\python"
        else:
            pip_path = "venv/bin/pip"
            python_path = "venv/bin/python"

        # Install dependencies
        print("📥 Installing dependencies...")
        subprocess.run([pip_path, "install", "-U", "pip"])
        subprocess.run([pip_path, "install", "-r", "requirements.txt"])
    else:
        print("✅ Already in virtual environment")
        pip_path = shutil.which("pip")
        python_path = sys.executable

        print("📥 Installing dependencies...")
        subprocess.run([pip_path, "install", "-U", "pip"])
        subprocess.run([pip_path, "install", "-r", "requirements.txt"])

    # Create directories
    print("📁 Creating directories...")
    (Path.cwd() / "data").mkdir(exist_ok=True)
    (Path.cwd() / "models").mkdir(exist_ok=True)

    # Download models
    print("⬇️  Downloading InsightFace models...")
    try:
        subprocess.run([python_path, "scripts/download_models.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Model download failed: {e}")
        print("   Models will be downloaded on first use.")

    # Check .env file
    env_file = Path.cwd() / ".env"
    if not env_file.exists():
        print("⚠️  .env file not found. Creating from template...")
        shutil.copy(".env.example", ".env")
        print("📝 Created .env file. Please update with your API keys.")
    else:
        print("✅ .env file exists")

    print("\n✅ Setup complete!")
    print("\n📚 Next steps:")
    print("1. Update .env file with your OpenAI API key")
    if not in_venv:
        print("2. Activate virtual environment:")
        if sys.platform == "win32":
            print("   .\\venv\\Scripts\\activate")
        else:
            print("   source venv/bin/activate")
    print(f"{'3' if not in_venv else '2'}. Run server: python -m src.main")
    print(f"{'4' if not in_venv else '3'}. Or use: make run")


if __name__ == "__main__":
    main()
