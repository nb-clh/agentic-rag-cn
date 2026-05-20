FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Install CPU-only torch from local wheel (avoids huge CUDA downloads)
COPY torch-2.12.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl /tmp/
RUN pip install --no-cache-dir /tmp/torch-2.12.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl && rm /tmp/torch-2.12.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl
# Install remaining deps from aliyun mirror
RUN pip install --no-cache-dir --retries 5 --timeout 300 \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
