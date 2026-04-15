"""
Run dbt commands with .env credentials injected into the environment.
dbt does not auto-load .env, so this wrapper handles it.

Usage:
    .venv/Scripts/python.exe run_dbt.py run
    .venv/Scripts/python.exe run_dbt.py test
    .venv/Scripts/python.exe run_dbt.py debug
    .venv/Scripts/python.exe run_dbt.py docs generate
    .venv/Scripts/python.exe run_dbt.py docs serve
"""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

project_root = Path(__file__).parent
dbt_project_dir = project_root / "basket_craft"
dbt_path = project_root / ".venv" / "Scripts" / "dbt.exe"

env = {**os.environ, **dotenv_values(project_root / ".env")}

args = sys.argv[1:]
result = subprocess.run(
    [str(dbt_path)] + args,
    env=env,
    cwd=str(dbt_project_dir),
)
sys.exit(result.returncode)
