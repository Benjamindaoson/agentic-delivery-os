#!/usr/bin/env python3
"""
One-command startup script for Agentic Delivery OS
Usage: python run.py [cli|api|web]
"""

import sys
import os
import subprocess
from pathlib import Path


def setup_environment():
    """Ensure dependencies are installed"""
    print("🔧 Checking environment...")
    requirements_file = Path("requirements.txt")
    
    if requirements_file.exists():
        print("📦 Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
    
    # Create necessary directories
    directories = [
        "artifacts/session",
        "artifacts/task_type",
        "artifacts/agent_profiles",
        "artifacts/tool_profiles",
        "artifacts/goals",
        "artifacts/eval",
        "artifacts/learning",
        "artifacts/registry",
        "memory/long_term",
        "benchmarks",
        "config"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Initialize registry
    print("📋 Loading configuration registry...")
    from runtime.registry.config_loader import ConfigRegistry
    registry = ConfigRegistry()
    registry.export_json()
    
    print("✅ Environment ready\n")


def run_cli():
    """Run CLI mode"""
    print("🖥️  CLI Mode - Use 'python agentctl.py --help' for commands\n")
    os.system(f"{sys.executable} agentctl.py --help")


def run_api():
    """Run API server"""
    print("🚀 Starting API Server on http://localhost:8000")
    print("📖 Docs available at http://localhost:8000/docs\n")
    os.system(f"{sys.executable} -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload")


def run_web():
    """Run Streamlit workbench"""
    print("🌐 Starting Workbench UI on http://localhost:8501\n")
    os.system(f"{sys.executable} -m streamlit run workbench_ui.py")


def show_help():
    """Show usage help"""
    print("""
🤖 Agentic Delivery OS - L5 Complete

Usage:
    python run.py [mode]

Modes:
    cli     - Command-line interface (agentctl)
    api     - REST API server (port 8000)
    web     - Streamlit workbench (port 8501)
    help    - Show this help message

Examples:
    python run.py web          # Start web UI
    python run.py api          # Start API server
    python agentctl.py run "What is AI?"  # CLI command
""")


def main():
    if len(sys.argv) < 2:
        mode = "web"  # Default to web UI
    else:
        mode = sys.argv[1].lower()
    
    # Setup environment first
    setup_environment()
    
    if mode == "cli":
        run_cli()
    elif mode == "api":
        run_api()
    elif mode == "web":
        run_web()
    elif mode == "help":
        show_help()
    else:
        print(f"❌ Unknown mode: {mode}")
        show_help()


if __name__ == "__main__":
    main()



