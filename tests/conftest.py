import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if int(pd.__version__.split(".")[0]) < 3:
    # pandas 2.x with NumPy 2.5 warns inside its own resample code, and warnings are errors here.
    pytest.exit(f"pandas {pd.__version__} found; requirements.txt needs pandas 3. Run `npm run setup` first.", returncode=4)
