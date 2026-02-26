#!/usr/bin/env python3
"""Test dependencies for new image generator."""

import sys
import importlib.util

def check_dependency(module_name, package_name=None):
    """Check if a module can be imported."""
    try:
        if importlib.util.find_spec(module_name) is not None:
            module = __import__(module_name)
            version = getattr(module, '__version__', 'unknown')
            print(f"✅ {module_name} (version: {version})")
            return True
        else:
            print(f"❌ {module_name} not found")
            return False
    except Exception as e:
        print(f"❌ {module_name} error: {e}")
        return False

def main():
    print("Checking dependencies for new image generator...")
    print("=" * 60)
    
    # Core dependencies
    deps = [
        ("jinja2", "jinja2"),
        ("playwright.async_api", "playwright"),
        ("pydub", "pydub"),
    ]
    
    all_ok = True
    for module_name, package_name in deps:
        all_ok = check_dependency(module_name, package_name) and all_ok
    
    print("=" * 60)
    
    # Check template directory
    import os
    from pathlib import Path
    
    template_path = Path(__file__).parent / "templates" / "reddit_post.html"
    if template_path.exists():
        print(f"✅ Template file found: {template_path}")
        print(f"   Size: {template_path.stat().st_size} bytes")
    else:
        print(f"❌ Template file not found: {template_path}")
        all_ok = False
    
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Running in a virtual environment")
    else:
        print("⚠️ Not running in a virtual environment (may use system packages)")
    
    print("=" * 60)
    
    if all_ok:
        print("All dependencies are available! ✓")
        return 0
    else:
        print("Some dependencies are missing!")
        print("\nTo install missing dependencies:")
        print("  pip install jinja2 playwright pydub")
        print("  playwright install chromium")
        return 1

if __name__ == "__main__":
    sys.exit(main())