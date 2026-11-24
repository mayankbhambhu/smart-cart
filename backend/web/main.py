"""The FreshFlow website: one address, one login page, three sections.

    /          the shop (shoppers) and the login page for everyone
    /store     Store Operations (worker, floor manager, store manager, owner)
    /admin     Admin (the FreshFlow platform team)

After signing in, the role on the account decides which section opens. Each section also checks the
role on every page, and the API checks it again on every request.

Run (from the backend/ folder):  uvicorn web.main:app --port 8001
"""
from fastapi import FastAPI

from web.admin.app import app as admin_section
from web.customer.app import app as shop_section
from web.store.app import app as store_section

app = FastAPI(title="FreshFlow", docs_url=None, redoc_url=None)
app.mount("/store", store_section)
app.mount("/admin", admin_section)
app.mount("/", shop_section)  # last: everything else, including /login and /static
