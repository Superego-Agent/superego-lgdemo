# config.py
"""
Configuration module for the Superego system.
This module contains configuration settings used across the application.
"""
from pathlib import Path

# Configuration
CONFIG = {
    "model_name": "claude-3-7-sonnet-latest",
    "file_paths": {
        "superego_instructions": "data/agent_instructions/input_superego.md",
        "inner_agent_instructions": "data/agent_instructions/inner_agent_default.md",
    },
    "streaming": True,
    "sessions_dir": "data/sessions",
    "constitutions_dir": "data/constitutions"
}

# Ensure directories exist
Path(CONFIG["sessions_dir"]).mkdir(parents=True, exist_ok=True)
Path(CONFIG["constitutions_dir"]).mkdir(parents=True, exist_ok=True)