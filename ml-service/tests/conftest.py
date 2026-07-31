import sys
from pathlib import Path

# ml-service/ has a hyphen in its name, so it can't be imported as a Python
# package (`import ml-service.mapping` is a syntax error). Add ml-service/
# itself to sys.path so `import mapping` works from test files, matching how
# app.py (which lives in the same directory) imports it.
sys.path.insert(0, str(Path(__file__).parent.parent))
