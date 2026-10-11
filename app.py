import sys
sys.dont_write_bytecode = True

import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from core.agent_graph import build_ncbi_kegg_graph
from core.memory_db import init_db, save_message, get_recent_messages, get_all_facts
from analytics.rhea_analytics import _load_all as preload_rhea_db
from pydantic import BaseModel

# Pre-load local Rhea database cache into RAM at startup
preload_rhea_db()

app = FastAPI(title="Bio-Inoscula API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static directory for the HTML frontend
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Build the global agent instance
agent = build_ncbi_kegg_graph()
init_db()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Streams the AI's response chunks back to the client using Server-Sent Events (SSE).
    """
    prompt = req.message

    # 1. Save user message to Episodic Memory
    save_message("user", prompt)

    # 2. Get Semantic Facts and inject them as a system message
    facts = get_all_facts()
    fact_context = ""
    if facts:
        fact_lines = [f"ID: {f[0]} | Fact: {f[1]}" for f in facts]
        fact_context = "CRITICAL: The user has defined the following permanent preferences/facts. You must adhere to them strictly:\n" + "\n".join(fact_lines) + "\n(To forget a fact, use tool_forget_fact with the ID)."

    # 3. Reconstruct the Sliding Window payload
    messages_payload = []
    if fact_context:
        messages_payload.append(("system", fact_context))

    recent_msgs = get_recent_messages(10)
    for role, msg in recent_msgs:
        messages_payload.append((role, msg))

    async def stream_generator():
        try:
            full_ai_response = ""
            for update in agent.stream(
                {"messages": messages_payload},
                config={"recursion_limit": 150},
                stream_mode="updates"
            ):
                if "agent" in update:
                    messages = update["agent"].get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, 'content') and last_msg.content:
                            chunk_text = ""
                            if isinstance(last_msg.content, str):
                                chunk_text = last_msg.content
                            elif isinstance(last_msg.content, list):
                                chunk_text = "".join(block.get("text", "") for block in last_msg.content if isinstance(block, dict))
                            
                            if chunk_text:
                                full_ai_response = chunk_text
                                import json
                                # Use JSON encoding so newlines in markdown aren't broken by the SSE protocol
                                payload = json.dumps({"chunk": chunk_text})
                                yield f"data: {payload}\n\n"
            
            # 4. Save AI's response to Episodic Memory once finished
            if full_ai_response:
                save_message("assistant", full_ai_response)
        except Exception as e:
            import json
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # How to run: python app.py or uv run uvicorn app:app --reload
    print("Starting Bio-Inoscula Backend Server...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
