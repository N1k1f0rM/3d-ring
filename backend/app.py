#!/usr/bin/env python3

import asyncio
import sys
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent))

from inference.infr import (
    parse_s3_uri,
    s3_client,
    stage_generate_3d,
    stage_remove_background,
    stage_sd_generate,
)

app = FastAPI(title="3D Generator")


@app.get("/generate")
async def generate(
    prompt: str = Query(..., min_length=3, description="Prompt for 3D model")
):
    try:
        run_id = uuid.uuid4().hex

        sd_uri = await asyncio.to_thread(stage_sd_generate, prompt, run_id)
        if not sd_uri:
            raise HTTPException(500, "Image not generated")

        ben2_uri = await asyncio.to_thread(stage_remove_background, sd_uri, run_id)
        if not ben2_uri:
            raise HTTPException(500, "Background remove failed")

        model_uri = await asyncio.to_thread(stage_generate_3d, ben2_uri, run_id)
        if not model_uri:
            raise HTTPException(500, "3D not generated")

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

        filename = f"3d_result_{run_id[:8]}.zip"
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(500, f"Внутренняя ошибка: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
