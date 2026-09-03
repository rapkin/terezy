"""``python -m terezy.api.http`` -- the supported way to start the service (020 FR-026b)."""

from __future__ import annotations

import sys

from terezy.api.http.serve import main

if __name__ == "__main__":
    sys.exit(main())
