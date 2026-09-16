#!/bin/bash
# 测试三种下载路径的速度
echo "=== 直连 GitHub release ==="
curl -s -o /dev/null -w "  code=%{http_code} speed=%{speed_download} B/s\n" --max-time 12 -r 0-3000000 -L https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx

echo "=== 走本地代理 7897 ==="
curl -s -o /dev/null -w "  code=%{http_code} speed=%{speed_download} B/s\n" --max-time 12 -x http://127.0.0.1:7897 -r 0-3000000 -L https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx

echo "=== hf-mirror 上的 RMBG-1.4 ==="
curl -s -o /dev/null -w "  code=%{http_code} speed=%{speed_download} B/s\n" --max-time 12 -r 0-3000000 -L https://hf-mirror.com/briaai/RMBG-1.4/resolve/main/onnx/model.onnx

echo "=== hf-mirror 上的 isnet-anime ==="
curl -s -o /dev/null -w "  code=%{http_code} speed=%{speed_download} B/s\n" --max-time 12 -r 0-3000000 -L https://hf-mirror.com/skytnt/anime-seg/resolve/main/isnetis.onnx
