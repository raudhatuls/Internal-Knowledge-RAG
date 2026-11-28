import json
import os
import psycopg
from pgvector.psycopg import register_vector

DATABASE_URL = os.getenv("DATABASE_URL")

with open("knowledge.json", "r", encoding="utf-8") as f:
    records = json.load(f)

with psycopg.connect(DATABASE_URL) as conn:
    register_vector(conn)

    for r in records:
        conn.execute(
            """
            INSERT INTO documents (
                id,
                content,
                embedding,
                source,
                document_name,
                step
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                r["id"],
                r["text"],
                r["vector"],
                r["metadata"]["sumber"],
                r["metadata"]["dokumen"],
                r["metadata"]["langkah"],
            ),
        )

    conn.commit()

print(f"Migrated {len(records)} records.")