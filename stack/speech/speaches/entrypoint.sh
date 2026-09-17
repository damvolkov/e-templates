#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://localhost:8000"
HEALTH_URL="${BASE_URL}/health"
MODELS_URL="${BASE_URL}/v1/models"

STT_MODEL="${WHISPER__MODEL:-deepdml/faster-whisper-large-v3-turbo-ct2}"
TTS_MODEL="${TTS_MODEL:-speaches-ai/Kokoro-82M-v1.0-ONNX}"

MAX_RETRIES=60
RETRY_INTERVAL=2

wait_for_health() {
    echo "[entrypoint] waiting for speaches to be healthy..."
    for i in $(seq 1 "$MAX_RETRIES"); do
        if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
            echo "[entrypoint] speaches is healthy"
            return 0
        fi
        sleep "$RETRY_INTERVAL"
    done
    echo "[entrypoint] speaches failed to become healthy after $((MAX_RETRIES * RETRY_INTERVAL))s"
    exit 1
}

download_model() {
    local model_id="$1"
    local label="$2"

    if curl -sf "${MODELS_URL}" 2>/dev/null | grep -q "\"${model_id}\""; then
        echo "[entrypoint] ${label} model already installed: ${model_id}"
        return 0
    fi

    echo "[entrypoint] downloading ${label} model: ${model_id} ..."
    if curl -sf -X POST "${MODELS_URL}/${model_id}" > /dev/null 2>&1; then
        echo "[entrypoint] ${label} model ready: ${model_id}"
    else
        echo "[entrypoint] WARNING: failed to download ${label} model: ${model_id}"
    fi
}

echo "[entrypoint] starting speaches server in background..."
uvicorn --factory --host 0.0.0.0 --port 8000 speaches.main:create_app &
SERVER_PID=$!

wait_for_health

download_model "$STT_MODEL" "STT"
download_model "$TTS_MODEL" "TTS"

echo "[entrypoint] all models ready — server PID ${SERVER_PID}"
wait "$SERVER_PID"
