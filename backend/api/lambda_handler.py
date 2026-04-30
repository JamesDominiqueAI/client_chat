from __future__ import annotations

from mangum import Mangum

from backend.api.main import app

handler = Mangum(app)
