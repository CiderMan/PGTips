import sys
from pathlib import Path

# The modules under test are not in a package, so put their directory on the path in the same
# way that pgtips.py does
sys.path.append(str(Path(__file__).resolve().parents[2] / "sub-modules"))
