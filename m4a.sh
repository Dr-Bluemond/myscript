#!/bin/bash


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
  local cover_image="$dir/${name}_COVER.png"
  local converted_dir="$dir/converted"

  echo "正在处理: $input_file"

  codec=$(ffprobe -v error -select_streams a:0 \
      -show_entries stream=codec_name \
      -of default=noprint_wrappers=1:nokey=1 \
      "$input_file")

  echo "实际编码格式: $codec"

    # 根据真实 codec 决定转码方式
  case "$codec" in
    flac)
      audio_codec="alac"
      ;;
    mp3)
      audio_codec="aac"
      ;;
    *)
      echo "⚠️ 不支持的实际音频编码: $codec，跳过 $input_file"
      return
      ;;
  esac

  # 提取封面
  ffmpeg -loglevel error -i "$input_file" -an -vcodec png "$cover_image"
  cover_status=$?

  if [ $cover_status -ne 0 ] || [ ! -f "$cover_image" ]; then
    echo "⚠️ 封面提取失败或不存在，将不嵌入封面"
  else
    echo "✅ 封面提取成功: $cover_image"
  fi

  if [ ! -f "$cover_image" ]; then
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

if [ $# -ne 1 ]; then
  input_path="/home/"
else
  input_path="$1"
fi

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