from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import httpx
import json

from app.security import require_user
from app.database import get_db
from app.models.models import User

router = APIRouter(prefix="/api/ai-proxy", tags=["ai-proxy"])

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

@router.post("/gemini/generateContent")
async def gemini_proxy(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Proxy endpoint for Gemini AI API.
    This endpoint forwards requests to the Gemini API using the backend-stored API key.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API key not configured on the server"
        )

    try:
        # Get the request body from the frontend
        body = await request.json()
        
        # Forward the request to Gemini API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GEMINI_API_URL,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": GEMINI_API_KEY
                },
                timeout=30.0  # Set a reasonable timeout
            )
        
        # If the Gemini API returns an error, propagate it
        if not response.is_success:
            # Try to get error details from Gemini's response
            error_detail = "Gemini API error"
            try:
                error_json = response.json()
                if "error" in error_json and "message" in error_json["error"]:
                    error_detail = error_json["error"]["message"]
            except:
                error_detail = response.text or error_detail
            
            raise HTTPException(
                status_code=response.status_code,
                detail=error_detail
            )
        
        # Return the response from Gemini
        return JSONResponse(content=response.json())
    
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with Gemini API: {str(exc)}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(exc)}"
        )