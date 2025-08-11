from fastapi import FastAPI, Request
import os
app = FastAPI()
@app.post('/webhook')
async def webhook(req: Request):
    _ = await req.json()
    return {"status":"ok"}
@app.get('/health')
async def health():
    return {"status":"ok"}
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5001)
