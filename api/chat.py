"""
Chat API Routes
Handles chat messages with sales-first routing.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from gateway import get_sales_router
from models import get_chemical_expert

logger = logging.getLogger("enpro.api.chat")

router = APIRouter(prefix="/api/v2", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for continuity")
    context: Optional[dict] = Field(None, description="Additional context (customer, industry, etc.)")
    show_reasoning: bool = Field(True, description="Include reasoning trace in response")


class ChatResponse(BaseModel):
    intent: str
    headline: str
    body: Optional[str]
    picks: list
    follow_up: Optional[str]
    reasoning_trace: Optional[list]
    model_used: str
    cost_usd: float
    latency_ms: float
    safety_flag: Optional[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message with sales-first routing.
    
    Routes to appropriate model based on intent:
    - pregame → o3-mini-high (strategic reasoning)
    - compare → o3-mini (side-by-side reasoning)
    - chemical → hardcoded lookup
    - lookup → fast lookup
    """
    try:
        sales_router = get_sales_router()
        
        result = await sales_router.route(
            message=request.message,
            context=request.context or {}
        )
        
        return ChatResponse(
            intent=result.intent,
            headline=result.headline,
            body=result.body,
            picks=result.picks,
            follow_up=result.follow_up,
            reasoning_trace=result.reasoning_trace if request.show_reasoning else None,
            model_used=result.model_used,
            cost_usd=result.cost,
            latency_ms=result.latency_ms,
            safety_flag=result.safety_flag
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pregame", response_model=ChatResponse)
async def pregame(request: ChatRequest):
    """
    Strategic pregame briefing with reasoning trace.
    
    Uses o3-mini-high to generate strategic meeting prep
    with visible reasoning trace for rep confidence.
    """
    try:
        sales_router = get_sales_router()
        
        # Force pregame intent
        result = await sales_router._handle_pregame(
            message=request.message,
            context=request.context or {}
        )
        
        return ChatResponse(
            intent="pregame",
            headline=result["headline"],
            body=result["body"],
            picks=result["picks"],
            follow_up=result["follow_up"],
            reasoning_trace=result["reasoning_trace"] if request.show_reasoning else None,
            model_used=result["model_used"],
            cost_usd=result["cost"],
            latency_ms=0.0,
            safety_flag=result.get("safety_flag")
        )
        
    except Exception as e:
        logger.error(f"Pregame error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare(parts: list[str], context: Optional[dict] = None):
    """
    Reasoning-driven product comparison.
    
    Shows side-by-side comparison with reasoning trace
    explaining the key differentiator.
    """
    try:
        sales_router = get_sales_router()
        
        message = f"compare {' and '.join(parts)}"
        result = await sales_router._handle_compare(
            message=message,
            context=context or {},
            history=[]
        )
        
        return {
            "headline": result["headline"],
            "comparison": json.loads(result["body"]) if result["body"] else {},
            "reasoning_trace": result["reasoning_trace"],
            "model_used": result["model_used"],
            "cost_usd": result["cost"]
        }
        
    except Exception as e:
        logger.error(f"Compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chemical/{chemical_name}")
async def chemical_lookup(chemical_name: str, concentration: Optional[str] = None):
    """
    Hardcoded chemical compatibility lookup.
    
    Zero AI cost - returns A/B/C/D ratings from hardcoded matrix.
    Unknown chemicals return escalation recommendation.
    """
    expert = get_chemical_expert()
    result = expert.lookup(chemical_name, concentration)
    
    return {
        "chemical": chemical_name,
        "concentration": concentration,
        **result
    }


@router.get("/stats")
async def get_stats():
    """Get router statistics including cost tracking."""
    sales_router = get_sales_router()
    return sales_router.get_stats()
