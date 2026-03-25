#!/usr/bin/env python3

import asyncio
import sys
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent))

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from inference.infr import (
    parse_s3_uri,
    s3_client,
    stage_generate_3d,
    stage_remove_background,
    stage_sd_generate,
)

generation_counter = Counter(
    "generation_total", "Total number of generations", ["status"]
)
generation_duration = Histogram(
    "generation_duration_seconds",
    "Generation duration in seconds",
    buckets=(30, 60, 120, 300, 600),
)

sd_duration = Histogram(
    "sd_duration_seconds",
    "Stable Diffusion stage duration",
    buckets=(10, 20, 40, 80, 160),
)
sd_counter = Counter("sd_total", "Stable Diffusion stage calls", ["status"])

ben2_duration = Histogram(
    "ben2_duration_seconds", "BEN2 stage duration", buckets=(5, 10, 20, 40, 80)
)
ben2_counter = Counter("ben2_total", "BEN2 stage calls", ["status"])

hunyuan_duration = Histogram(
    "hunyuan_duration_seconds",
    "Hunyuan3D stage duration",
    buckets=(60, 120, 180, 300, 600),
)
hunyuan_counter = Counter("hunyuan_total", "Hunyuan3D stage calls", ["status"])

active_generations = Gauge(
    "active_generations", "Number of currently running generations"
)

app = FastAPI()


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/generate")
async def generate(
    prompt: str = Query(..., min_length=3, description="Prompt for 3D model")
):

    generation_counter.labels("started").inc()
    start = time.time()
    active_generations.inc()

    try:

        run_id = uuid.uuid4()

        sd_counter.labels("started").inc()
        sd_start = time.time()
        sd_uri = await asyncio.to_thread(stage_sd_generate, prompt, run_id)
        sd_duration.observe(time.time() - sd_start)
        if not sd_uri:
            sd_counter.labels("failed").inc()
            raise HTTPException(500, "Image not generated")
        sd_counter.labels("succeed").inc()

        ben2_counter.labels("started").inc()
        ben2_start = time.time()
        ben2_uri = await asyncio.to_thread(stage_remove_background, sd_uri, run_id)
        ben2_duration.observe(time.time() - ben2_start)
        if not ben2_uri:
            ben2_counter.labels("failed").inc()
            raise HTTPException(500, "Background remove failed")
        ben2_counter.labels("succeed").inc()

        hunyuan_counter.labels("started").inc()
        h_start = time.time()
        model_uri = await asyncio.to_thread(stage_generate_3d, ben2_uri, run_id)
        hunyuan_duration.observe(h_start - time.time())
        if not model_uri:
            hunyuan_counter.labels("failed").inc()
            raise HTTPException(500, "3D not generated")
        hunyuan_counter.labels("succeed").inc()

        bucket_img, key_img = parse_s3_uri(sd_uri)
        img_obj = s3_client.get_object(Bucket=bucket_img, Key=key_img)
        img_data = img_obj["Body"].read()

        bucket_model, key_model = parse_s3_uri(model_uri)
        model_obj = s3_client.get_object(Bucket=bucket_model, Key=key_model)
        model_data = model_obj["Body"].read()

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("generated.png", img_data)
            zf.writestr("model.stl", model_data)
        zip_buffer.seek(0)

        generation_duration.observe(time.time() - start)
        generation_counter.labels(status="success").inc()

        filename = f"3d_result_{run_id[:8]}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        generation_counter.labels(status="failed").inc()
        raise HTTPException(500, f"Внутренняя ошибка: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
