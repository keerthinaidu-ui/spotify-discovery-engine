import sys
import subprocess
import importlib
from pathlib import Path

print("=" * 70)
print("APP SCRAPER COMPATIBILITY CHECK")
print("=" * 70)

print(f"Python version : {sys.version}")
print(f"Python exe     : {sys.executable}")
print(f"Working folder : {Path.cwd()}")
print()

if sys.version_info < (3, 8):
    print("FAIL: Python is too old for a modern setup.")
else:
    print("OK: Python version is usable.")
print()

packages_to_check = [
    "app_store_scraper",
    "requests",
    "urllib3",
    "six",
    "pandas",
]

for pkg in packages_to_check:
    try:
        mod = importlib.import_module(pkg)
        version = getattr(mod, "__version__", "version not exposed")
        location = getattr(mod, "__file__", "location unknown")
        print(f"OK: {pkg}")
        print(f"   version  : {version}")
        print(f"   location : {location}")
    except Exception as e:
        print(f"FAIL: {pkg}")
        print(f"   error    : {repr(e)}")

print()
print("-" * 70)
print("PIP SHOW RESULTS")
print("-" * 70)

for pip_name in ["app-store-scraper", "requests", "urllib3", "six", "pandas"]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", pip_name],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            print(result.stdout)
        else:
            print(f"Package not found by pip show: {pip_name}")
    except Exception as e:
        print(f"Could not run pip show for {pip_name}: {e}")

print("-" * 70)
print("APP STORE SCRAPER IMPORT TEST")
print("-" * 70)

try:
    from app_store_scraper import AppStore
    print("OK: from app_store_scraper import AppStore")
    print("Your environment appears compatible enough to import the scraper.")
except Exception as e:
    print("FAIL: Could not import AppStore")
    print(repr(e))

print()
print("Done.")