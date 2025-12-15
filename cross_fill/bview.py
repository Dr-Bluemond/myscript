#!/root/venv/bin/python
"""
bview.py - 用 bencodepy 解码指定文件并漂亮打印（处理 bytes 显示）
用法:
    python3 bview.py path/to/file.fastresume
"""
import sys
import argparse
import pprint
import bencodepy
import binascii

TRUNC_HEX_LEN = 64 # 十六进制前缀长度（字符数，不是字节数）

def bytes_preview(b: bytes) -> str:
    """尝试把 bytes 解为 utf-8 字符串，否则返回简短 hex/len 表示。"""
    try:
        s = b.decode('utf-8')
        # 可判断是否包含不可打印字符，如果是则仍当作二进制处理
        if any(ord(c) < 9 for c in s):
            raise UnicodeDecodeError("control", b, 0, 1, "control")
        return s
    except Exception:
        hexed = binascii.hexlify(b).decode('ascii')
        if len(hexed) > TRUNC_HEX_LEN:
            hex_preview = hexed[:TRUNC_HEX_LEN] + "..."
        else:
            hex_preview = hexed
        return f"<bytes len={len(b)} hex={hex_preview}>"

def normalize(value):
    """
    将 bencodepy 解码得到的数据结构转换为更可读的 Python 结构：
    - bytes -> 尝试 utf-8 字符串，否则简短 hex 表示
    - dict keys (bytes) -> 尝试转为 str（utf-8），否则保留为 bytes_preview 表示
    """
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        # 这里单独返回 bytes 的可读预览
        return bytes_preview(value)
    if isinstance(value, list) or isinstance(value, tuple):
        return [normalize(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            # 处理 key（通常是 bytes）
            if isinstance(k, bytes):
                try:
                    key = k.decode('utf-8')
                except Exception:
                    key = bytes_preview(k)
            else:
                key = k

            out[key] = normalize(v)
        return out
    # 兜底
    return str(value)

def main():
    parser = argparse.ArgumentParser(description="Decode bencoded file and pretty-print (handles bytes).")
    parser.add_argument("file", help="path to bencoded file (torrent / fastresume / etc.)")
    args = parser.parse_args()

    path = args.file
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except Exception as e:
        print(f"Failed to read file {path}: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        decoded = bencodepy.decode(raw)
    except Exception as e:
        print(f"Failed to decode bencoded data: {e}", file=sys.stderr)
        sys.exit(3)

    norm = normalize(decoded)

    pp = pprint.PrettyPrinter(indent=2, width=120, compact=False)
    pp.pprint(norm)

if __name__ == "__main__":
    main()
