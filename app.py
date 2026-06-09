# ============================================================
# FILE: app.py
# PURPOSE: Application entry point — creates and runs Flask app
# LAST UPDATED: Phase 1
# ============================================================

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)