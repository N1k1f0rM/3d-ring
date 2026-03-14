import base64
import io
import os
import zipfile
from io import BytesIO
from pathlib import Path

import boto3
import plotly.graph_objects as go
import requests
import streamlit as st
import trimesh
from botocore.client import Config
from dotenv import load_dotenv

st.set_page_config(
    page_title="3D Ring Generator",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    endpoint_url=f"http://localhost:9000",
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name=AWS_DEFAULT_REGION,
)


def get_stl_bytes(stl_input):

    if isinstance(stl_input, str):
        if "," in stl_input:
            stl_input = stl_input.split(",")[1]
        return base64.b64decode(stl_input)
    elif isinstance(stl_input, bytes):
        return stl_input
    else:
        st.error(f"{type(stl_input)}")
        return None


def load_mesh_from_stl(stl_input):

    stl_bytes = get_stl_bytes(stl_input)
    if stl_bytes is None:
        return None
    try:
        mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl")
        return mesh
    except Exception as e:
        st.error(f"{e}")
        return None


def get_stl_info(mesh):

    if mesh is None:
        return None
    info = {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "volume": f"{mesh.volume:.2f}",
        "bounds": (
            [f"{b:.2f}" for b in mesh.bounds.flatten()]
            if mesh.bounds is not None
            else "N/A"
        ),
        "is_watertight": mesh.is_watertight,
    }
    return info


def create_plotly_mesh(mesh):

    if mesh is None:
        return None
    vertices = mesh.vertices
    faces = mesh.faces
    fig = go.Figure(
        data=[
            go.Mesh3d(
                x=vertices[:, 0],
                y=vertices[:, 1],
                z=vertices[:, 2],
                i=faces[:, 0],
                j=faces[:, 1],
                k=faces[:, 2],
                color="grey",
                opacity=0.8,
                flatshading=True,
                lighting=dict(ambient=0.8, diffuse=0.8),
                lightposition=dict(x=100, y=100, z=100),
            )
        ]
    )
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode=False,
    )
    return fig


def get_image_bytes(img_input):

    if isinstance(img_input, str):
        if "," in img_input:
            img_input = img_input.split(",")[1]
        return base64.b64decode(img_input)
    elif isinstance(img_input, bytes):
        return img_input
    else:
        return None


st.markdown(
    """
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 3rem;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        font-size: 1.1rem;
        padding: 0.75rem;
        border: none;
        border-radius: 10px;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #764ba2 0%, #667eea 100%);
    }
    .success-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)


def parse_s3_uri(uri: str):

    if uri.startswith("s3://"):
        parts = uri[5:].split("/", 1)
        return parts[0], parts[1]
    raise ValueError(f"S3 URI: {uri}")


def download_from_minio(s3_uri: str):

    bucket, key = parse_s3_uri(s3_uri)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def generate_3d_model(prompt: str, backend_url: str = "http://localhost:8000"):

    try:
        response = requests.get(
            f"{backend_url}/generate",
            params={"prompt": prompt},
            timeout=1800,  # 30 минут
        )
        response.raise_for_status()
        return response.content
    except requests.exceptions.Timeout:
        st.error("Too long")
        return None
    except Exception as e:
        st.error(f"Generation error {str(e)}")
        return None


st.markdown(
    '<div class="main-header">💍 3D Ring Generator</div>', unsafe_allow_html=True
)
st.markdown(
    '<div class="sub-header">Создавайте уникальные 3D модели колец с помощью ИИ</div>',
    unsafe_allow_html=True,
)


backend_url = st.text_input(
    "Backend URL", value="http://localhost:8000", help="URL вашего FastAPI backend"
)


with st.form(key="generation_form", clear_on_submit=False):
    col1, col2 = st.columns([4, 1])
    with col1:
        prompt = st.text_input(
            " Опишите ваше кольцо",
            placeholder="Например: beautiful silver ring with lion head, no bokeh effect",
            label_visibility="collapsed",
        )
    with col2:
        submit_button = st.form_submit_button("🚀 Сгенерировать", width="stretch")

if submit_button and prompt:
    if not prompt.strip():
        st.warning("⚠️ Пожалуйста, введите описание кольца")
    else:
        with st.spinner("Генерируем 3D модель... Это может занять 2-5 минут"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.text("📸 Этап 1/3: Генерация 2D изображения...")
            progress_bar.progress(33)

            status_text.text("✂️ Этап 2/3: Удаление фона...")
            progress_bar.progress(66)

            status_text.text("🧊 Этап 3/3: Создание 3D модели...")
            progress_bar.progress(90)

            zip_data = generate_3d_model(prompt, backend_url)

            if zip_data:
                progress_bar.progress(100)
                status_text.text("✅ Готово!")

                with zipfile.ZipFile(BytesIO(zip_data), "r") as zf:
                    img_data = None
                    stl_data = None

                    for filename in zf.namelist():
                        if filename.endswith(".png"):
                            img_data = zf.read(filename)
                        elif filename.endswith(".stl"):
                            stl_data = zf.read(filename)

                st.success("🎉 3D модель успешно сгенерирована!")

                col_left, col_right = st.columns(2)

                with col_left:
                    st.subheader("📸 Сгенерированное изображение")
                    if img_data:
                        st.image(img_data, width="stretch")

                        st.download_button(
                            label="📥 Скачать PNG",
                            data=img_data,
                            file_name="generated_ring.png",
                            mime="image/png",
                            width="stretch",
                        )

                with col_right:
                    st.subheader("🎮 3D Model (STL)")

                    if stl_data:

                        stl_bytes = get_stl_bytes(stl_data)
                        if stl_bytes is None:
                            st.error("No STL data")
                        else:
                            st.info(f"📦 Size: {len(stl_bytes) / 1024:.2f} KB")

                            mesh = load_mesh_from_stl(stl_data)

                            if mesh is not None:
                                tab1, tab2, tab3 = st.tabs(
                                    ["🔍 Interactive 3D", "📊 Info", "📥 Download"]
                                )

                                with tab1:
                                    fig = create_plotly_mesh(mesh)
                                    if fig:
                                        st.plotly_chart(fig, width="stretch")
                                    else:
                                        st.warning("Don't visualized")

                                with tab2:
                                    info = get_stl_info(mesh)
                                    if info:
                                        st.markdown("#### Characters:")
                                        st.write(f"**Vertices:** {info['vertices']:,}")
                                        st.write(f"**Faces:** {info['faces']:,}")
                                        st.write(f"**Volume:** {info['volume']}")
                                        st.write(
                                            f"**Bounds (xmin, xmax, ymin, ymax, zmin, zmax):** {info['bounds']}"
                                        )
                                    else:
                                        st.warning("No info")

                                with tab3:
                                    st.markdown("#### Download STL")
                                    st.download_button(
                                        label="📥 Download STL",
                                        data=stl_bytes,
                                        file_name="model.stl",
                                        mime="application/sla",
                                        width="stretch",
                                    )

                                with st.expander("📊 Info generation"):
                                    st.write(f"**Prompt:** {prompt}")
                                    if img_data:
                                        img_bytes = get_image_bytes(img_data)
                                        if img_bytes:
                                            st.write(
                                                f"**Size PNG:** {len(img_bytes) / 1024:.2f} KB"
                                            )
                                    st.write(
                                        f"**Size STL:** {len(stl_bytes) / 1024:.2f} KB"
                                    )
                            else:
                                st.error("Check format")
                    else:
                        st.warning("Generate before")

elif submit_button and not prompt:
    st.warning("⚠️ Пожалуйста, введите описание кольца")

st.markdown("---")

st.markdown("---")
st.markdown(
    """
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p>💍 3D Ring Generator</p>
</div>
""",
    unsafe_allow_html=True,
)
