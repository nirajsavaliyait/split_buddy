import os
import uvicorn


def main():
    port = int(os.getenv("PORT", "8001"))
    from main import app
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
