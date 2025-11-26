#!/usr/bin/env python3
"""Script to run the V2G Marketplace API server."""

import uvicorn


def main():
    """Run the FastAPI server."""
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
