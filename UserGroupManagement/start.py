import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    # Proxy headers ensure correct client IPs/host when behind Railway's proxy
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
