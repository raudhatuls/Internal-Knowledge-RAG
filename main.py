from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
import numpy as np
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"
ANSWER_MODEL = "gpt-6-luna"
STORE = "knowledge.json"
SYSTEM_PROMPT = f"""
        Jawab pertanyaan dengan ramah dan profesional
        Jawab pertanyaan sesuai dengan potongan knowledge yang dikasih
        Jika tidak ada jawaban jawab tidak tahu jangan mengarang informasi apapun
        Jika jawaban bisa lebih dari satu klarifikasi dan
        jelaskan dua aturan berbeda secara terpisah, dan sebutkan nama dokumen di akhir jawaban 
        """
        
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SKIP_PREFIX = ("PT NUSANTARA GAYA KREATIF", "Kode Dokumen:")
STEP = re.compile(r"^(\d+)\.\s+(.*)$")

def answer(records, question, n):
    model_input = "Pertanyaan : "+question+"\n"
    for score, r in query(records, question, n=n):
        model_input=model_input+(f"{score:.3f}  {r['text'][:200]}")+"\n"
    response = client.responses.create(
                        model=ANSWER_MODEL,
                        instructions=SYSTEM_PROMPT,
                        input=model_input
                )
    return response.output_text
    
def is_section(line):
    if line.endswith(":") and len(line) <= 80:
        return True
    return (bool(re.match(r"^\d+\.\s", line))
            and len(line) <= 80
            and ":" not in line
            and not line.endswith("."))


def chunk_with_context(text):
    chunks, dokumen, section, pending = [], "", "", []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith(SKIP_PREFIX):
            continue
        if line.startswith("DOKUMEN "):
            dokumen, section, pending = line, "", []
            continue
        if is_section(line):
            section, pending = line.rstrip(":"), []
            continue

        step = None
        m = STEP.match(line)
        if m:
            step, line = int(m.group(1)), m.group(2)
            pending = []  # item bernomor baru tidak mewarisi pengantar

        if line.endswith(":"):
            pending.append(line)
            continue

        text_line = " ".join(pending + [line]) if pending else line
        prefix = " | ".join(x for x in (dokumen, section) if x)
        chunks.append({
            "text": f"[{prefix}] {text_line}" if prefix else text_line,
            "dokumen": dokumen,
            "langkah": step,
        })
    return chunks

def embed(texts):
    resp = client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [d.embedding for d in resp.data]


def build_store():
    with open("knowledge.txt", "r", encoding="utf-8") as f:
        items = chunk_with_context(f.read())
    vectors = embed([it["text"] for it in items])
    records = [
        {
            "id": f"c{i}",
            "text": it["text"],
            "vector": v,
            "metadata": {
                "sumber": "SOP_NUSAwear.docx",
                "dokumen": it["dokumen"],
                "langkah": it["langkah"],
            },
        }
        for i, (it, v) in enumerate(zip(items, vectors), 1)
    ]
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    print("store dibuat:", len(records), "chunk")
    return records


def load_store():
    if not os.path.exists(STORE):
        return build_store()
    with open(STORE, "r", encoding="utf-8") as f:
        return json.load(f)


def query(records, question, n=2, where=None):
    q = np.array(embed([question])[0])
    candidates = [
        r for r in records
        if where is None or all(r["metadata"].get(k) == v for k, v in where.items())
    ]
    scored = []
    for r in candidates:
        v = np.array(r["vector"])
        score = np.dot(v, q) / (np.linalg.norm(v) * np.linalg.norm(q))
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:n]


def print_chunks(path="knowledge.txt"):
    with open(path, "r", encoding="utf-8") as f:
        items = chunk_with_context(f.read())
    for i, it in enumerate(items, 1):
        langkah = f" langkah={it['langkah']}" if it["langkah"] else ""
        print(f"[{i:02d}]{langkah} {it['text']}")
    print(f"\nTotal chunk: {len(items)}")

if __name__ == "__main__":
    records = load_store()
    # print_chunks()
    for pertanyaan in [
        "jam kerja jam berapa?",
        "jam cut-off pengiriman jam berapa?",
        "kalau barang rusak, ongkir retur siapa yang bayar?",
        "nomor hr berapa?",
    ]:
    # answer(records, "jam kerja jam ber/apa?")
        print(f"\n=== {pertanyaan}")
        print(answer(records, pertanyaan, n=5))
        for score, r in query(records, pertanyaan, n=5):
            print(f"{score:.3f}  {r['text'][:200]}")