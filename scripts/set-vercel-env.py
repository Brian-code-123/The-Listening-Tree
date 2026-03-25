#!/usr/bin/env python3
"""
set-vercel-env.py — Automatically set environment variables in Vercel

This script reads .env file and configures them in Vercel for Production environment.
Requires: Vercel CLI installed and authenticated.

Usage:
    python scripts/set-vercel-env.py

Optional: Provide DATABASE_URL:
    DATABASE_URL="sqlite:///prod.db" python scripts/set-vercel-env.py
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

def load_env_file(env_path: str = ".env") -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"❌ {env_path} not found")
        sys.exit(1)
    return env_vars

def run_command(cmd: List[str], stdin_data: str = None) -> Tuple[int, str, str]:
    """Execute a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_data.encode() if stdin_data else None,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)

def set_env_var(key: str, value: str) -> bool:
    """Set an environment variable in Vercel for Production."""
    print(f"  Setting {key}...", end=" ", flush=True)
    
    # Use echo to pass the value via stdin to avoid shell escaping issues
    cmd = [
        "bash", "-c",
        f"echo '{value}' | vercel env add {key} production --yes"
    ]
    
    exit_code, stdout, stderr = run_command(cmd)
    
    if exit_code == 0:
        print("✅")
        return True
    else:
        print(f"❌\n    Error: {stderr.strip()}")
        return False

def verify_env_vars() -> bool:
    """Verify that environment variables are set in Vercel."""
    print("\n[5/5] Verifying environment variables in Vercel...")
    
    cmd = ["vercel", "env", "ls"]
    exit_code, stdout, stderr = run_command(cmd)
    
    if exit_code == 0:
        print("✅ Environment variables set:")
        for line in stdout.strip().split("\n"):
            if "Encrypted" in line:
                print(f"   • {line.strip()}")
        return True
    else:
        print(f"❌ Failed to list variables: {stderr}")
        return False

def main():
    print("\n" + "="*60)
    print("🚀 The Listening Tree — Vercel Environment Setup")
    print("="*60 + "\n")
    
    # Step 1: Verify vercel CLI
    print("[1/5] Verifying Vercel CLI...")
    exit_code, stdout, _ = run_command(["vercel", "--version"])
    if exit_code != 0:
        print("❌ Vercel CLI not found. Install with: brew install vercel")
        sys.exit(1)
    print(f"✅ {stdout.strip()}\n")
    
    # Step 2: Verify authentication
    print("[2/5] Verifying Vercel authentication...")
    exit_code, stdout, stderr = run_command(["vercel", "whoami"])
    if exit_code != 0 or "Error" in stdout:
        print("❌ Not authenticated. Run: vercel login")
        sys.exit(1)
    user_name = stdout.strip().split("\n")[-1]
    print(f"✅ Authenticated as: {user_name}\n")
    
    # Step 3: Load .env file
    print("[3/5] Loading environment variables from .env...")
    env_vars = load_env_file(".env")
    
    if not env_vars:
        print("❌ No variables found in .env")
        sys.exit(1)
    
    print(f"✅ Loaded {len(env_vars)} variables:")
    for key in env_vars:
        value_preview = env_vars[key][:20] + "..." if len(env_vars[key]) > 20 else env_vars[key]
        print(f"   • {key} = {value_preview}")
    print()
    
    # Step 4: Set variables in Vercel
    print("[4/5] Setting environment variables in Vercel (Production)...")
    
    success_count = 0
    failed_vars = []
    
    for key, value in env_vars.items():
        if set_env_var(key, value):
            success_count += 1
        else:
            failed_vars.append(key)
    
    print(f"\n✅ Successfully set {success_count}/{len(env_vars)} variables")
    
    if failed_vars:
        print(f"❌ Failed variables: {', '.join(failed_vars)}")
        print("\nTry setting them manually:")
        for key in failed_vars:
            print(f"  vercel env add {key} production --yes")
    
    # Step 5: Verify
    if verify_env_vars():
        print("\n" + "="*60)
        print("✅ Environment setup complete!")
        print("="*60)
        print("\nNext steps:")
        print("  1. Deploy to Vercel:")
        print("     git push origin main")
        print("  2. Or manually deploy:")
        print("     vercel deploy --prod")
        print("  3. Verify health endpoints:")
        print("     curl https://your-project.vercel.app/health")
        print()
    else:
        print("\n❌ Could not verify environment variables")
        sys.exit(1)

if __name__ == "__main__":
    with open(".env", "r") as f:
        if not f.read().strip():
            print("❌ .env file is empty")
            sys.exit(1)
    main()
