import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# 既存のモジュールをインポート
from core import run_batch
import asyncio

app = FastAPI()

# CORS設定（Webサイトからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可（本番ではGitHub PagesのURLに絞るべき）
    allow_methods=["*"],
    allow_headers=["*"],
)

# 状態管理
class State:
    is_running = False
    stop_flag = False
    logs = []

state = State()

class StartReq(BaseModel):
    count: int
    password: str
    headless: bool

def log_callback(msg, level="INFO"):
    """Web用にログをメモリに保存"""
    print(f"[{level}] {msg}")
    state.logs.append({"msg": msg, "level": level})
    # ログが増えすぎないように制限
    if len(state.logs) > 100:
        state.logs.pop(0)

def worker(count, headless, password):
    state.is_running = True
    state.stop_flag = False
    
    # core.py の run_batch は async なので同期的に回す
    try:
        asyncio.run(run_batch(
            count, headless, password, 
            log_callback, 
            lambda: state.stop_flag
        ))
    except Exception as e:
        log_callback(f"Server Error: {str(e)}", "ERR")
    finally:
        state.is_running = False
        log_callback("Process finished.", "INFO")

@app.post("/start")
def start_process(req: StartReq):
    if state.is_running:
        return {"status": "error", "message": "Already running"}
    
    state.logs.clear() # ログリセット
    t = threading.Thread(target=worker, args=(req.count, req.headless, req.password))
    t.start()
    return {"status": "ok", "message": "Started processing..."}

@app.post("/stop")
def stop_process():
    if state.is_running:
        state.stop_flag = True
        return {"status": "ok", "message": "Stopping..."}
    return {"status": "ignored", "message": "Not running"}

@app.get("/logs")
def get_logs():
    # 取得したログを返して、サーバー側メモリからは消す（ポーリング用）
    # ※簡易実装のため、ここでは消さずに最新10件を返す方式でもよいが、
    #  今回は「渡した分は消す」方式にする
    current_logs = state.logs[:]
    state.logs.clear()
    return {"lines": current_logs}

if __name__ == "__main__":
    import uvicorn
    # localhost:8000 でサーバー起動
    uvicorn.run(app, host="0.0.0.0", port=8000)
