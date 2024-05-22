#! /usr/bin/env python3
from pathlib import Path

from plc import PlcTester

import appdirs
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from typing import Any


from pydantic import BaseModel


class TextData(BaseModel):
    data: str


SERVICE_NAME = "PLC Extension"

app = FastAPI(
    title="PLC Extension API",
    description="API for the PLC extension",
)

logger.info(f"Starting {SERVICE_NAME}!")
tester = PlcTester()

@app.get("/devices", status_code=status.HTTP_200_OK)
@version(1, 0)
async def detect_devices() -> Any:
  return tester.detect_devices()

@app.get("/tonemap", status_code=status.HTTP_200_OK)
@version(1, 0)
async def tonemap() -> Any:
  return tester.read_tonemap()


@app.get("/rate", status_code=status.HTTP_200_OK)
@version(1, 0)
async def tonemap() -> Any:
  return tester.read_rates()


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

app.mount("/", StaticFiles(directory="static",html = True), name="static")

@app.get("/", response_class=FileResponse)
async def root() -> Any:
        return "index.html"

if __name__ == "__main__":
    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=1142, log_config=None)