#!/root/venv/bin/python
import sys
import os
import bencodepy
from pathlib import Path


def load_fastresume(hash_hex):
    p = f"{hash_hex}.fastresume"
    with open(p, "rb") as f:
        d = bencodepy.decode(f.read())
    return d, p


def load_torrent(hash_hex):
    p = f"{hash_hex}.torrent"
    with open(p, "rb") as f:
        d = bencodepy.decode(f.read())
    return d, p


def get_file_path(fast):
    return Path(fast[b"qBt-savePath"].decode()) / fast[b"qBt-name"].decode()


def cross_fill(objs):
    #
    # 打开文件和元信息
    #
    for o in objs:
        info = o["torrent"][b"info"]
        o["piece_len"] = info[b"piece length"]
        o["file_len"] = info[b"length"]
        
        pieces = None
        fast = o["fast"]

        if b"pieces" in fast:
            pieces = fast[b"pieces"]

        if not isinstance(pieces, (bytes, bytearray)):
            raise TypeError(f"unexpected pieces format in fastresume for {o['hash']}: {type(pieces)}")

        # pieces 即为 bitfield：每 bit 一块，1=存在，0=不存在
        # 但为了简单，我们按 bview 一样直接使用底层 bytes，并在内存中修改
        o["bitfield"] = bytearray(pieces)
        o["piece_count"] = len(o["bitfield"])

        o["file_path"] = get_file_path(o["fast"])
        o["fp"] = open(o["file_path"], "r+b")


    # 按块大小从小到大排序，便于优先用小块补大块
    objs.sort(key=lambda x: x["piece_len"])


    for B in objs: # 作为补全源
        for A in objs: # 作为被补全目标
            if A is B:
                continue

            plen_a = A["piece_len"]
            plen_b = B["piece_len"]

            bf_a = A["bitfield"]
            bf_b = B["bitfield"]

            for i in range(A["piece_count"]):
                if bf_a[i] == 1:
                    continue

                startA = i * plen_a
                endA = min(startA + plen_a, A["file_len"])

                # 检查 B 是否完整覆盖 A 的 piece
                pos = startA
                ok = True

                while pos < endA:
                    j = pos // plen_b
                    if j >= len(bf_b) or bf_b[j] == 0:
                        ok = False
                        break
                    pos = (j + 1) * plen_b

                if not ok:
                    continue

                # 读取 B 的对应部分
                buf = bytearray(endA - startA)
                pos = startA
                while pos < endA:
                    j = pos // plen_b
                    j_start = j * plen_b
                    j_end = min(j_start + plen_b, B["file_len"])

                    overlap_start = pos
                    overlap_end = min(j_end, endA)
                    sz = overlap_end - overlap_start

                    B["fp"].seek(overlap_start)
                    buf[overlap_start - startA : overlap_start - startA + sz] = B["fp"].read(sz)

                    pos = overlap_end

                # 写入 A
                A["fp"].seek(startA)
                A["fp"].write(buf)

                # 标记 A 的 bitfield（已补完该 piece，仅在内存中）

                A["bitfield"][i] = 1


                print(f"[+] {A['hash']}: 补全 piece {i} <- {B['hash']}")

    for o in objs:
        o["fp"].close()
        print(f"[√] 完成文件：{o['file_path']}")


def main():
    if len(sys.argv) < 3:
        print("Usage: cross_fill.py <hash1> <hash2> [...]")
        sys.exit(1)

    objs = []
    for h in sys.argv[1:]:
        fast, fp_fast = load_fastresume(h)
        tor, fp_tor = load_torrent(h)

        objs.append({
            "hash": h,
            "fast": fast,
            "torrent": tor,
        })

    cross_fill(objs)
    print("\n请回到 qBittorrent 对所有任务执行一次【重新检查】以更新位图\n")


if __name__ == "__main__":
    main()

