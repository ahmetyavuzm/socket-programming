#!/usr/bin/env bash
set -e

echo "🔍 Checking for Python 3.9..."

# Dinamik olarak python3.9 binary’sini bulmaya çalış
PYTHON_BIN="$(command -v python3.9 || true)"

if [ -z "$PYTHON_BIN" ]; then
    echo "⚠️ Python 3.9 not found — installing..."
    if command -v brew &>/dev/null; then
        brew install python@3.9
        # brew, genelde /opt/homebrew veya /usr/local altında kurar
        PYTHON_BIN="$(brew --prefix python@3.9)/bin/python3.9"
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3.9 python3.9-venv python3.9-distutils
        PYTHON_BIN="$(command -v python3.9)"
    elif command -v yum &>/dev/null; then
        sudo yum install -y python39
        PYTHON_BIN="$(command -v python3.9)"
    else
        echo "❌ Could not install Python 3.9 automatically. Install it manually."
        exit 1
    fi
fi

# Eğer halen bulunamadıysa, hata ver
if [ ! -x "$PYTHON_BIN" ]; then
    echo "❌ Python 3.9 binary not found after installation."
    echo "Please ensure it’s in your PATH."
    exit 1
fi

echo "🐍 Using Python binary: $PYTHON_BIN"

# Sanal ortamı oluştur
echo "📦 Creating virtual environment..."
"$PYTHON_BIN" -m venv env
source env/bin/activate

# Pip ve paketleri kur
echo "⬆️  Upgrading pip and installing dependencies..."
pip install --upgrade pip
pip install rich colorama

echo "✅ Environment setup complete."
echo "👉 To activate later, run: source env/bin/activate"
