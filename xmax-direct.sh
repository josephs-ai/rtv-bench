#!/bin/bash
# xmax-direct.sh — pin Xmax hosts to the physical gateway so they bypass the VPN.
# Re-derives the gateway each run, so it survives network changes.
#
#   sudo ./xmax-direct.sh add
#   sudo ./xmax-direct.sh remove
#   ./xmax-direct.sh status

set -uo pipefail

HOSTS=(platform.xmaxai.com api.xmaxai.com)
STATE=/tmp/xmax-direct.routes

gateway() {
    # physical default gateway on en0 (ignores VPN 0/1 + 128.0/1 split routes)
    netstat -rn -f inet | awk '$1=="default" && $NF=="en0" {print $2; exit}'
}

resolve() {
    for h in "${HOSTS[@]}"; do
        dig +short "$h" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
    done | sort -u
}

case "${1:-}" in
add)
    GW=$(gateway)
    if [ -z "$GW" ]; then
        echo "No en0 default gateway found. Is Wi-Fi/Ethernet up?" >&2
        exit 1
    fi
    echo "Physical gateway: $GW"
    : > "$STATE"
    for ip in $(resolve); do
        route -n delete -host "$ip" >/dev/null 2>&1
        if route -n add -host "$ip" "$GW" >/dev/null 2>&1; then
            echo "$ip" >> "$STATE"
            iface=$(route -n get "$ip" 2>/dev/null | awk '/interface:/{print $2}')
            echo "  $ip -> $iface"
        else
            echo "  $ip FAILED" >&2
        fi
    done
    ;;
remove)
    if [ -f "$STATE" ]; then
        while read -r ip; do
            route -n delete -host "$ip" >/dev/null 2>&1 && echo "  removed $ip"
        done < "$STATE"
        rm -f "$STATE"
    else
        echo "No recorded routes; removing by current DNS instead."
        for ip in $(resolve); do
            route -n delete -host "$ip" >/dev/null 2>&1 && echo "  removed $ip"
        done
    fi
    ;;
status)
    for ip in $(resolve); do
        iface=$(route -n get "$ip" 2>/dev/null | awk '/interface:/{print $2}')
        echo "$ip -> ${iface:-unknown}"
    done
    ;;
*)
    echo "usage: $0 {add|remove|status}   (add/remove need sudo)" >&2
    exit 1
    ;;
esac
