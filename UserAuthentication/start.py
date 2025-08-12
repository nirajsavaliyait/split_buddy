import os
import uvicorn


def main():
    port = int(os.getenv("PORT", "8001"))
    from main import app
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level="info",
    )


if __name__ == "__main__":
    main()
