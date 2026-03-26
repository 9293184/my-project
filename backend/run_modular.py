import os

from aisec_app import create_app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "y"}
    app.run(host=host, port=port, debug=debug)
