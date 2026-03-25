#!/usr/bin/env python3

import gc
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import boto3
import torch
from botocore.client import Config
from diffusers import StableDiffusionPipeline
from dotenv import load_dotenv
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.texgen import Hunyuan3DPaintPipeline
from PIL import Image

from ben2 import BEN_Base

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    endpoint_url="minio:9000",
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name=AWS_DEFAULT_REGION,
)


BUCKET_SD = "sd-res"
BUCKET_BEN2 = "ben2"
BUCKET_HUNYUAN = "hunyuan"


def generate_object_name(run_id: str, prefix: str, extension: str) -> str:

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{prefix}_{timestamp}_{unique_id}.{extension.lstrip('.')}"
    return f"{run_id}/{filename}"


def parse_s3_uri(uri: str):

    if uri.startswith("s3://"):
        parts = uri[5:].split("/", 1)
        return parts[0], parts[1]
    raise ValueError(f"Incorrect S3 URI: {uri}")


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

SD_MODEL = "runwayml/stable-diffusion-v1-5"
BEN2_MODEL = "PramaLLC/BEN2"
HUNYUAN_MODEL = "tencent/Hunyuan3D-2"

SD_STEPS = 20
SD_GUIDANCE = 7.0
REFINE_FOREGROUND = False
ADD_TEXTURE = False
TIMEOUT_PER_STAGE = 600


def log(stage: str, message: str, level: str = "INFO"):
    timestamp = time.strftime("%H:%M:%S")
    prefix = {"INFO": "info", "WARN": "warn", "ERROR": "err", "SUCCESS": "success"}[
        level
    ]
    print(f"[{timestamp}] [{stage}] {prefix} {message}", flush=True)


def timeout_handler(signum, frame):
    raise TimeoutError("Time limit")


def check_memory(stage: str):
    if DEVICE == "cuda":
        free_mem = torch.cuda.get_device_properties(
            0
        ).total_memory - torch.cuda.memory_allocated(0)
        free_gb = free_mem / 1e9
        log(stage, f"VRAM: {free_gb:.2f} ГБ")
        if free_gb < 4:
            log(stage, "Low memory", "WARN")


def stage_sd_generate(prompt: str, run_id: str) -> str:
    log("SD", f"Генерация: '{prompt[:50]}...'")
    check_memory("SD")
    start = time.time()

    try:
        pipe = StableDiffusionPipeline.from_pretrained(
            SD_MODEL,
            torch_dtype=DTYPE,
            use_safetensors=True,
            local_files_only=False,
        )
        pipe = pipe.to(DEVICE)
        pipe.enable_attention_slicing()

        if DEVICE == "cuda" and torch.cuda.get_device_properties(0).total_memory < 12e9:
            pipe.enable_sequential_cpu_offload(gpu_id=0)

        image = pipe(
            prompt=prompt, num_inference_steps=SD_STEPS, guidance_scale=SD_GUIDANCE
        ).images[0]

        temp_file = f"/tmp/sd_{uuid.uuid4().hex}.png"
        image.save(temp_file)

        object_name = generate_object_name(run_id, "sd", "png")
        s3_client.upload_file(
            Filename=temp_file,
            Bucket=BUCKET_SD,
            Key=object_name,
            ExtraArgs={"ContentType": "image/png"},
        )

        os.remove(temp_file)
        object_uri = f"s3://{BUCKET_SD}/{object_name}"
        log("SD", f"Ready {time.time()-start:.1f}s → {object_uri}")

        del pipe
        gc.collect()
        if DEVICE == "cuda":
            torch.cuda.empty_cache()
        return object_uri

    except Exception as e:
        log("SD", f"Err: {type(e).__name__}: {e}", "ERROR")
        return None


def stage_remove_background(input_uri: str, run_id: str) -> str:
    log("BEN2", f"Remove background: {input_uri}")
    check_memory("BEN2")
    input_bucket, input_object = parse_s3_uri(input_uri)

    start = time.time()

    try:
        local_input = f"/tmp/ben2_input_{uuid.uuid4().hex}.png"
        s3_client.download_file(
            Bucket=input_bucket, Key=input_object, Filename=local_input
        )

        model = BEN_Base.from_pretrained(BEN2_MODEL)
        model.to(DEVICE).eval()

        image = Image.open(local_input).convert("RGB")
        foreground = model.inference(image, refine_foreground=REFINE_FOREGROUND)

        if foreground.mode == "RGBA":
            bg = Image.new("RGBA", foreground.size, (255, 255, 255, 255))
            bg.paste(foreground, mask=foreground.split()[3])
            foreground = bg.convert("RGB")

        local_output = f"/tmp/ben2_output_{uuid.uuid4().hex}.png"
        foreground.save(local_output)

        object_name = generate_object_name(run_id, "ben2", "png")
        s3_client.upload_file(
            Filename=local_output,
            Bucket=BUCKET_BEN2,
            Key=object_name,
            ExtraArgs={"ContentType": "image/png"},
        )

        os.remove(local_input)
        os.remove(local_output)

        object_uri = f"s3://{BUCKET_BEN2}/{object_name}"
        log("BEN2", f"Ready {time.time()-start:.1f}s → {object_uri}")

        del model
        gc.collect()
        if DEVICE == "cuda":
            torch.cuda.empty_cache()
        return object_uri

    except Exception as e:
        log("BEN2", f"Err {type(e).__name__}: {e}", "ERROR")
        return None


def stage_generate_3d(input_uri: str, run_id: str) -> str:
    log("Hunyuan3D", f"🧊 Генерация 3D: {input_uri}")
    check_memory("Hunyuan3D")
    input_bucket, input_object = parse_s3_uri(input_uri)

    start = time.time()

    try:
        local_input = f"/tmp/hunyuan_input_{uuid.uuid4().hex}.png"
        s3_client.download_file(
            Bucket=input_bucket, Key=input_object, Filename=local_input
        )

        shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            HUNYUAN_MODEL,
            torch_dtype=DTYPE,
            local_files_only=False,
        )
        mesh = shape_pipe(image=local_input)[0]

        if ADD_TEXTURE:
            tex_pipe = Hunyuan3DPaintPipeline.from_pretrained(HUNYUAN_MODEL)
            mesh = tex_pipe(mesh, image=local_input)
            del tex_pipe

        output_ext = ".stl"
        local_output = f"/tmp/hunyuan_output_{uuid.uuid4().hex}{output_ext}"
        mesh.export(local_output)

        object_name = generate_object_name(run_id, "hunyuan", output_ext.lstrip("."))
        content_type = "application/sla"

        s3_client.upload_file(
            Filename=local_output,
            Bucket=BUCKET_HUNYUAN,
            Key=object_name,
            ExtraArgs={"ContentType": content_type},
        )

        os.remove(local_input)
        os.remove(local_output)

        object_uri = f"s3://{BUCKET_HUNYUAN}/{object_name}"
        log("Hunyuan3D", f"Ready {time.time()-start:.1f}s → {object_uri}")

        del shape_pipe, mesh
        gc.collect()
        if DEVICE == "cuda":
            torch.cuda.empty_cache()
        return object_uri

    except Exception as e:
        log("Hunyuan3D", f"Err {type(e).__name__}: {e}", "ERROR")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("Starting Pipe")
    test_run_id = uuid.uuid4().hex
    sd = stage_sd_generate("beautiful ring silver", test_run_id)
    if sd:
        ben = stage_remove_background(sd, test_run_id)
        if ben:
            model = stage_generate_3d(ben, test_run_id)
            if model:
                print(f"\n Ready {model}")
