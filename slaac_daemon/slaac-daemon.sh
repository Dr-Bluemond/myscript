#!/bin/bash
# 简易 SLAAC 动态守护脚本
# 自动检测 IPv6 前缀变化并更新地址
# 依赖: rdisc6, ip, awk, grep, cut

IFACE="$1"
STATEFILE="/run/slaac-${IFACE}.prefix"

get_prefix() {
    rdisc6 -1 -q "$IFACE" 2>/dev/null | cut -d/ -f1
}

apply_address() {
    local prefix="$1"
    local addr="${prefix}1"

    echo "[`date '+%F %T'`] applying prefix: $prefix"
    ip -6 addr flush dev "$IFACE" scope global
    ip -6 addr add "${addr}/64" dev "$IFACE"
    ip -6 route replace default via fe80::1 dev "$IFACE"
}

monitor_ra() {
    echo "[`date '+%F %T'`] Listening for RA on $IFACE using radvdump..."
    radvdump 2>/dev/null | while read -r line; do
        # 匹配前缀行，去掉前导空格
        if [[ "$line" =~ ^[[:space:]]*prefix[[:space:]]+([0-9a-fA-F:]+)\/[0-9]+ ]]; then
            prefix="${BASH_REMATCH[1]}"
            echo "[`date '+%F %T'`] Prefix received: $prefix"
            oldprefix=$(cat "$STATEFILE" 2>/dev/null)
            if [ "$prefix" != "$oldprefix" ]; then
                echo "[`date '+%F %T'`] Prefix changed from $oldprefix to $prefix"
                echo "$prefix" > "$STATEFILE"
                apply_address "$prefix"
            fi
        fi
    done
}

main() {
    echo "[`date '+%F %T'`] SLAAC daemon starting on $IFACE"
    prefix=$(get_prefix)
    if [ -n "$prefix" ]; then
        echo "$prefix" > "$STATEFILE"
        apply_address "$prefix"
    fi
    monitor_ra
}

main