#!/bin/bash
mkdir -p ~/.rembg/models/isnet-anime
cd ~/.rembg/models/isnet-anime
curl -L -C - --retry 5 --retry-delay 3 -x http://127.0.0.1:7897 \
  -o isnet-anime.onnx \
  https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
echo "下载结束，文件大小："
ls -la isnet-anime.onnx
