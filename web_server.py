from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

app = FastAPI()

# Mount the static files directory
app.mount("/web", StaticFiles(directory="web"), name="web")

@app.get("/")
async def read_root():
    return {"message": "Health Buddy WebApp Server"}

@app.get("/web/add_med.html", response_class=HTMLResponse)
async def read_add_med_form():
    with open(os.path.join("web", "add_med.html"), "r") as f:
        return f.read()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
