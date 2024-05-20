#!/bin/sh -e

# Get the absolute path to the current script
script_dir=$(cd "$(dirname "$0")" && pwd)
cd "$script_dir"

# Check for necessary commands and Python version
command -v python3 >/dev/null 2>&1 || { echo >&2 "Python3 is not installed. Aborting."; exit 1; }

# Check Python version meets minimum requirement (e.g., Python 3.3+)
python_version_ok=$(python3 -c 'import sys; print(sys.version_info >= (3, 3))')
if [ "$python_version_ok" != "True" ]; then
  echo >&2 "Python 3.3 or higher is required for venv. Aborting."
  exit 1
fi

# Check if Python venv module is available
python3 -c 'import venv' 2>/dev/null || { echo >&2 "Python venv module is not available. Aborting."; exit 1; }

# Define virtual environment directory
venv_path="$script_dir/.python-ve"

# Check if virtual environment directory exists
if [ ! -d "$venv_path" ]; then
  echo "Creating virtual environment in $venv_path..."
  python3 -m venv "$venv_path"
  # Activate virtual environment and install requirements
  # shellcheck disable=SC1091
  . "$venv_path/bin/activate"
  pip install -r requirements.txt
  deactivate
fi

# Activate virtual environment and run the script
# shellcheck disable=SC1091
. "$venv_path/bin/activate"
python "$script_dir/generate_ssh_config.py" "$@"
deactivate