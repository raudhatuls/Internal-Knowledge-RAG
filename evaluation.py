import json, os
from main import answer
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal

load_dotenv()

ANSWER_MODEL = "gpt-6-luna"
SYSTEM_PROMPT = f"""
                Evaluate the quality of a RAG system. Determine whether the test passes or fails 
                based on the question, expected answer, actual answer, and sources provided to you. 
                Return the response in JSON format as follows:
                 "result" : "pass | fail", "reason" : "a short reason here"
                 What to check :
                 - Does the actual answer correctly address the question compared with the expected answer?
                 - Are the factual claims in the actual answer supported by the retrieved context?
                 Different wording does not automatically mean failure.
                 Missing important information should count as failure.
                 Unsupported factual claims should count as failure.
                 If the context doesn't contain the answer, an appropriate refusal should pass.
                 Don't require the actual answer to be identical to the expected answer.
            """
class JudgeResult(BaseModel):
    result: Literal["pass", "fail"]
    reason: str

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def judge(question, expected, actual, sources):
    readable_source = format_for_readable_text(sources)
    context = "question : "+question+". Expected result : "+expected+". Actual : "+actual+ ". Sources: "
    context = context+readable_source
    response = client.responses.parse(
            model=ANSWER_MODEL,
            instructions=SYSTEM_PROMPT,
            input=context,
            text_format=JudgeResult
        )
    parsed = response.output_parsed
    if parsed is None:
        return {"result": "fail", "reason": "Gagal mem-parsing output judge."}
    return parsed.model_dump()
    
    
def get_actual_response():    
    with open("evaluation.json", "r", encoding="utf-8") as f:
        cases = json.load(f)
        results = []
        for c in cases:
            actual_response, source = answer(c["question"], n=5)
            print("=" * 60)
            print("Question : ",c["question"])
            print("Expected answer :", c["expected_answer"])
            print("Actual response : ", actual_response)
            scoring = judge(c["question"], c["expected_answer"], actual_response, source)
            results.append(scoring["result"])
            if scoring["result"] == "fail":
                print("Retrieved sources:")
                print(format_for_readable_text(source))
    
    passed = sum(1 for r in results if r == "pass")
    print("=" * 60)
    print("Summary : ")
    print("Total: ", len(results))
    print("Passed: ", passed)
    print("Failed: ", len(results) - passed)
    Akurasi = (passed / len(results)) * 100 if len(results) > 0 else 0.0
    print(f"Accuracy: {Akurasi:.2f}%")

def format_for_readable_text(items: list[dict]) -> str:
  blocks = []
  for i, item in enumerate(items, start=1):
    doc = (item.get("dokumen") or "Dokumen Tidak Diketahui").strip()
    teks = item.get("teks", "").strip()

    # Jika di dalam 'teks' sudah ada prefix [DOKUMEN ... | Bagian ...], pisahkan agar lebih rapi
    if teks.startswith("[") and "] " in teks:
      meta, isi = teks[1:].split("] ", 1)
      blocks.append(f"[Chunk {i} | Sumber: {meta}]\n{isi}")
    else:
      blocks.append(f"[Chunk {i} | Dokumen: {doc}]\n{teks}")

  return "\n\n---\n\n".join(blocks)

if __name__ == "__main__":
    get_actual_response()
