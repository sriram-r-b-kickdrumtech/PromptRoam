#!/bin/bash
set -e

echo "--- 🚀 STARTING PROMPTROAM SETUP (AWS/LINUX) ---"

# 1. Update and install basic dependencies
echo "Updating system and installing base tools..."
sudo apt-get update -y
sudo apt-get install -y git curl build-essential libssl-dev zlib1g-dev 
    libbz2-dev libreadline-dev libsqlite3-dev wget llvm 
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# 2. Setup Node.js (for frontend) if not installed
if ! command -v npm &> /dev/null; then
    echo "Installing Node.js and NPM..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# 3. Setup Miniconda if not installed
if ! command -v conda &> /dev/null; then
    echo "Installing Miniconda..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p $HOME/miniconda
    rm miniconda.sh
    export PATH="$HOME/miniconda/bin:$PATH"
    # Source conda immediately for the rest of the script
    source "$HOME/miniconda/etc/profile.d/conda.sh"
    conda init bash
else
    echo "Conda already installed. Initializing..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
fi

# 4. Create/Update Conda Environment
echo "Setting up Conda environment 'promptroam'..."
if conda info --envs | grep -q "promptroam"; then
    conda env update -f environment.yml --prune
else
    conda env create -f environment.yml
fi

# 5. Initialize .env from example if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  CRITICAL: Update .env with your real API keys before running!"
fi

# 6. Build Frontend
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo ""
echo "--- ✅ SETUP COMPLETE ---"
echo "To start the application:"
echo "1. conda activate promptroam"
echo "2. python -m app.main"
echo ""
echo "--- 🚀 HAPPY ROAMING ---"
