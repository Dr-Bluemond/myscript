#!/bin/bash

# 用法说明
if [ $# -ne 1 ]; then
  echo "用法: $0 <音频文件或目录的绝对路径>"
  exit 1
fi

input_path="$1"

# 处理单个文件
process_file() {
  local input_file="$1"
  local filename_lower=$(basename "$input_file" | tr 'A-Z' 'a-z')

  if [[ "$filename_lower" != *.flac && "$filename_lower" != *.mp3 ]]; then
    echo "跳过（不支持的文件类型）: $input_file"
    return
  fi

  if [ ! -f "$input_file" ]; then
    echo "错误：文件不存在：$input_file"
    return
  fi

  local dir=$(dirname "$input_file")
  local base=$(basename "$input_file")
  local name="${base%.*}"
  local ext="${base##*.}"
  local ext_lower=$(echo "$ext" | tr 'A-Z' 'a-z')
  local output_file="$dir/$name.m4a"
  local cover_image="$dir/${name}_cover.jpg"
  local converted_dir="$dir/converted"

  echo "正在处理: $input_file"

  # 提取封面
  ffmpeg -loglevel error -i "$input_file" -an -vcodec copy "$cover_image"

  if [ "$ext_lower" == "flac" ]; then
    audio_codec="alac"
  elif [ "$ext_lower" == "mp3" ]; then
    audio_codec="aac"
  fi

  if [ ! -f "$cover_image" ]; then
    echo "⚠️ 未找到封面图像，将不嵌入封面"
    ffmpeg -loglevel error -i "$input_file" -vn -c:a "$audio_codec" "$output_file"
  else
    ffmpeg -loglevel error \
      -i "$input_file" \
      -i "$cover_image" \
      -map 0:a \
      -map 1:v \
      -c:a "$audio_codec" \
      -c:v png \
      -disposition:v attached_pic \
      "$output_file"
    rm -f "$cover_image"
  fi

  conversion_success=$?

  if [ "$conversion_success" -eq 0 ]; then
    mkdir -p "$converted_dir"
    mv "$input_file" "$converted_dir"
    echo "✅ 完成: $output_file"
  else
    echo "❌ 转换失败，保留原文件: $input_file"
    rm -f "$output_file"
  fi
}

# 如果是目录，则遍历
if [ -d "$input_path" ]; then
  for file in "$input_path"/*; do
    if [ -f "$file" ]; then
      process_file "$file"
    fi
  done
elif [ -f "$input_path" ]; then
  process_file "$input_path"
else
  echo "错误：输入路径无效：$input_path"
  exit 1
fi

