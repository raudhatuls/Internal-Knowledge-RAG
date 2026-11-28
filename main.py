from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
from openai import OpenAI
import psycopg
from pgvector.psycopg import register_vector
from pgvector import Vector


EMBED_MODEL = "text-embedding-3-small"
ANSWER_MODEL = "gpt-6-luna"
DATABASE_URL = os.getenv("DATABASE_URL")
STORE = "knowledge.json"
SYSTEM_PROMPT = f"""
        Answer the question in a friendly and professional manner.
            If there is no answer, state that you do not know professionally.
            Do not fabricate any information.
            If commonly used abbreviations appear, check for matches in the chunks.
            If the question is ambiguous and multiple relevant rules apply, ask for clarification before answering.
            If the relevant rules can be distinguished based on conditions, explain each rule separately.
            If the question mentions something not explicitly stated in the chunks, do not infer it from related data. State that it is not available, then mention the closest available information, such as regular working hours.
            State the source document name at the end, but if no answer is found, do not mention any source document.
            Copy numbers, hours, minutes, and other deadlines exactly as written in the chunks. Do not round or truncate them.
            If the answer exists in any of the chunks, answer directly. Do not state that it is not mentioned.
            Do not add Markdown.
        """
        
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SKIP_PREFIX = ("PT NUSANTARA GAYA KREATIF", "Kode Dokumen:")
STEP = re.compile(r"^(\d+)\.\s+(.*)$")

def answer(question, n=5):
    hits = query(question, n=n)

    model_input = "Pertanyaan : " + question + "\n"

    for score, r in hits:
        model_input += f"{score:.3f}  {r['text']}\n"

    response = client.responses.create(
        model=ANSWER_MODEL,
        instructions=SYSTEM_PROMPT,
        input=model_input,
    )

    sources = [
        {
            "dokumen": r["metadata"]["dokumen"],
            "teks": r["text"],
        }
        for _, r in hits
    ]

    return response.output_text, sources
    
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


def query(question, n=3, where=None):
    q = Vector(embed([question])[0])

    sql = """
        SELECT
            id,
            content,
            source,
            document_name,
            step,
            1 - (embedding <=> %s) AS score
        FROM documents
    """

    params = [q]

    if where:
        column_mapping = {
            "sumber": "source",
            "dokumen": "document_name",
            "langkah": "step",
        }

        filters = []

        for key, value in where.items():
            column = column_mapping.get(key)

            if column is None:
                raise ValueError(f"Filter tidak dikenal: {key}")

            filters.append(f"{column} = %s")
            params.append(value)

        sql += " WHERE " + " AND ".join(filters)

    sql += """
        ORDER BY embedding <=> %s
        LIMIT %s
    """

    params.extend([q, n])

    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)

        rows = conn.execute(sql, params).fetchall()

    return [
        (
            float(row[5]),
            {
                "id": row[0],
                "text": row[1],
                "metadata": {
                    "sumber": row[2],
                    "dokumen": row[3],
                    "langkah": row[4],
                },
            },
        )
        for row in rows
    ]


def print_chunks(path="knowledge.txt"):
    with open(path, "r", encoding="utf-8") as f:
        items = chunk_with_context(f.read())
    for i, it in enumerate(items, 1):
        langkah = f" langkah={it['langkah']}" if it["langkah"] else ""
        print(f"[{i:02d}]{langkah} {it['text']}")
    print(f"\nTotal chunk: {len(items)}")

