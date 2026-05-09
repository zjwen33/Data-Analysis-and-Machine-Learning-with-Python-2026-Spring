import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from review_fetcher import get_place_and_reviews, load_api_keys, extract_data_id
from review_processor import analyze_and_get_results
from decision_maker import generate_decision_report

app = FastAPI(title="Google Maps Review Analyzer API")

# Serve static files for the frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    """直接回傳前端首頁 HTML，不改變網址"""
    return FileResponse("static/index.html")

class AnalyzeRequest(BaseModel):
    url: str

@app.post("/api/analyze")
async def analyze_url(req: AnalyzeRequest):
    url = req.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        # Step 0: Extract data_id
        data_id = extract_data_id(url)
        if not data_id:
            raise HTTPException(status_code=400, detail="Invalid Google Maps URL: Cannot extract data_id")

        # Step 1: Fetch
        api_keys = load_api_keys()
        if not api_keys:
            # If no API keys, perhaps fail or return mock?
            # We fail for real.
            raise HTTPException(status_code=500, detail="Server is missing API keys")
            
        hl_lang = "zh-tw"
        try:
            get_place_and_reviews(url, hl_lang, api_keys)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

        # Step 2: Process
        analyze_and_get_results(data_id, hl_lang)

        # Step 3: Generate Report
        report = generate_decision_report(data_id, hl_lang)
        if not report:
            raise HTTPException(status_code=500, detail="Failed to generate report")

        return {"status": "success", "data": report}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
