from ccc.api.routes import router
from ccc.config import ROLE_PERMISSIONS, settings
from harness.app import create_app

app = create_app(title="Cyber Command Center API", version="0.2.0", settings=settings,
                 role_permissions=ROLE_PERMISSIONS, routers=[router],
                 description="Enterprise asset intelligence. See docs/PRD.pdf §8 for the full API contract.")
