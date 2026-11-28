from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from main import answer
import time
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("rag")

app = FastAPI(title="NUSAwear Knowledge Assistant")
LIMIT = 20          # pertanyaan per IP
WINDOW = 24 * 3600  # per 24 jam
hits = defaultdict(list)

def allowed(ip):
    now = time.time()
    hits[ip] = [t for t in hits[ip] if now - t < WINDOW]
    if len(hits[ip]) >= LIMIT:
        return False
    hits[ip].append(now)
    return True

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=300)


@app.get("/")
def index():
    return FileResponse("index.html")

@app.post("/ask")
def ask(req: AskRequest, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    if not allowed(ip):
        log.warning("Batas pertanyaan hari ini sudah tercapai. Coba lagi besok.")
        raise HTTPException(status_code=429, detail="Batas pertanyaan hari ini sudah tercapai. Coba lagi besok.")
    try:
        start = time.time()
        text, sources = answer(req.question, n=5)
        log.info("ask len=%d sources=%d ms=%.1f", len(req.question), len(sources), (time.time() - start) * 1000)
    except Exception as e:
        log.error("gagal memproses pertanyaan (len=%d): %s", len(req.question), type(e).__name__)
        raise HTTPException(status_code=500, detail="Gagal memproses pertanyaan. Coba lagi.")
    return {"answer": text, "sources": sources}