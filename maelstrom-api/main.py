#!/usr/bin/env python3
"""
Maelstrom REST API Shim
Provides orchestration endpoints for monitoring plane management
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials  
from fastapi.responses import JSONResponse
import httpx
import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Maelstrom Orchestration API",
    description="Central monitoring plane management API",
    version="1.0.0"
)

# Security
security = HTTPBasic()

# Configuration
RESURGENT_IP = os.getenv("RESURGENT_IP", "192.168.1.115")
API_USERNAME = os.getenv("API_USERNAME", "maelstrom_admin")
# Do not default to a hardcoded password; require environment to set it
API_PASSWORD = os.getenv("API_PASSWORD")

# Cache for diagnostic data
diagnostic_cache: Dict[str, Any] = {}
cache_ttl = 60  # seconds

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify API authentication"""
    correct_username = API_USERNAME
    correct_password = API_PASSWORD
    if correct_password is None:
        # Misconfiguration: no API password configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API password not configured; set API_PASSWORD env var",
            headers={"Retry-After": "60"},
        )
    
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/")
async def root():
    """API health check"""
    return {
        "service": "Maelstrom Orchestration API",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "resurgent_ip": RESURGENT_IP,
        "cache_entries": len(diagnostic_cache),
        "uptime": time.time()
    }

@app.get("/targets")
async def get_prometheus_targets(username: str = Depends(verify_credentials)):
    """Generate Prometheus file service discovery JSON"""
    logger.info(f"Generating Prometheus targets for user: {username}")
    
    targets = [
        {
            "targets": [f"{RESURGENT_IP}:9100", f"{RESURGENT_IP}:8081"],
            "labels": {
                "env": "prod",
                "site": "homelab", 
                "host_role": "unraid",
                "host": "resurgent",
                "managed_by": "maelstrom"
            }
        },
        {
            "targets": ["localhost:9090", "localhost:9093", "localhost:3000"],
            "labels": {
                "env": "prod",
                "site": "homelab",
                "host_role": "monitoring",
                "host": "maelstrom",
                "managed_by": "maelstrom"
            }
        }
    ]
    
    return JSONResponse(content=targets)

@app.get("/proxy/resurgent/diag")
async def proxy_resurgent_diagnostics(username: str = Depends(verify_credentials)):
    """Proxy diagnostic data from Resurgent with caching"""
    cache_key = "resurgent_diag"
    current_time = time.time()
    
    # Check cache
    if cache_key in diagnostic_cache:
        cache_entry = diagnostic_cache[cache_key]
        if current_time - cache_entry["timestamp"] < cache_ttl:
            logger.info("Returning cached Resurgent diagnostics")
            return cache_entry["data"]
    
    # Fetch fresh data
    try:
        logger.info(f"Fetching diagnostics from Resurgent ({RESURGENT_IP})")
        
        # Try multiple endpoints that might exist on Resurgent
        endpoints_to_try = [
            f"http://{RESURGENT_IP}:8080/api/diagnostics",
            f"http://{RESURGENT_IP}:9090/api/v1/status/buildinfo",
            f"http://{RESURGENT_IP}:3000/api/health",
        ]
        
        diag_data = {
            "host": "resurgent",
            "ip": RESURGENT_IP,
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "endpoints": {}
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in endpoints_to_try:
                try:
                    response = await client.get(endpoint)
                    diag_data["endpoints"][endpoint] = {
                        "status_code": response.status_code,
                        "accessible": response.status_code == 200,
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000)
                    }
                    if response.status_code == 200:
                        diag_data["status"] = "accessible"
                except Exception as e:
                    diag_data["endpoints"][endpoint] = {
                        "status_code": 0,
                        "accessible": False,
                        "error": str(e)
                    }
        
        # Check basic connectivity
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Test if any HTTP service responds
                response = await client.get(f"http://{RESURGENT_IP}:80")
                diag_data["basic_http"] = True
        except:
            diag_data["basic_http"] = False
            
        # Update cache
        diagnostic_cache[cache_key] = {
            "data": diag_data,
            "timestamp": current_time
        }
        
        logger.info(f"Cached fresh diagnostics for Resurgent")
        return diag_data
        
    except Exception as e:
        logger.error(f"Failed to fetch Resurgent diagnostics: {str(e)}")
        return {
            "host": "resurgent", 
            "ip": RESURGENT_IP,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }

@app.post("/approve/action")
async def approve_action(
    action_request: Dict[str, Any],
    username: str = Depends(verify_credentials)
):
    """Record action approval intent (stub implementation)"""
    logger.info(f"Action approval request from {username}: {action_request}")
    
    # Validate required fields
    required_fields = ["action_type", "target", "justification"]
    missing_fields = [field for field in required_fields if field not in action_request]
    
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {missing_fields}"
        )
    
    # Create approval record
    approval_record = {
        "id": f"approval_{int(time.time())}",
        "timestamp": datetime.now().isoformat(),
        "approved_by": username,
        "action_type": action_request["action_type"],
        "target": action_request["target"],
        "justification": action_request["justification"],
        "status": "pending",
        "auto_execute": False  # Manual approval required
    }
    
    # In a real implementation, this would be stored in a database
    # For now, just log it
    logger.info(f"Approval recorded: {approval_record}")
    
    return {
        "approval_id": approval_record["id"],
        "status": "recorded",
        "message": "Action approval recorded, manual execution required",
        "next_steps": "Action will not be executed automatically. Manual intervention required."
    }

@app.get("/approvals")
async def list_approvals(username: str = Depends(verify_credentials)):
    """List pending approvals (stub implementation)"""
    # In a real implementation, this would query the database
    return {
        "pending_approvals": [],
        "message": "No pending approvals (stub implementation)"
    }

@app.get("/metrics")
async def get_api_metrics():
    """API metrics endpoint for Prometheus scraping"""
    return {
        "maelstrom_api_requests_total": 0,
        "maelstrom_api_cache_hits_total": len(diagnostic_cache),
        "maelstrom_api_uptime_seconds": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
