#!/usr/bin/env bash
# Privileged netplan helper called by basin-api via sudo.
# Reads JSON from stdin: {"interface":"eth0","address":"192.168.1.10","prefix":24,"gateway":"192.168.1.1","dns":["8.8.8.8"]}
# Writes /etc/netplan/99-basin.yaml and applies it.
set -euo pipefail

INPUT="$(cat)"

IFACE="$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['interface'])")"
ADDRESS="$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['address'])")"
PREFIX="$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['prefix'])")"
GATEWAY="$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('gateway',''))")"
DNS="$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(','.join(d.get('dns',[])))")"

# Validate interface exists
if ! ip link show "$IFACE" &>/dev/null; then
    echo "Unknown interface: $IFACE" >&2
    exit 1
fi

cat > /etc/netplan/99-basin.yaml <<EOF
network:
  version: 2
  ethernets:
    ${IFACE}:
      addresses:
        - ${ADDRESS}/${PREFIX}
$([ -n "$GATEWAY" ] && echo "      routes:" || true)
$([ -n "$GATEWAY" ] && echo "        - to: default" || true)
$([ -n "$GATEWAY" ] && echo "          via: ${GATEWAY}" || true)
$([ -n "$DNS" ] && echo "      nameservers:" || true)
$([ -n "$DNS" ] && echo "        addresses: [${DNS}]" || true)
EOF

chmod 600 /etc/netplan/99-basin.yaml
netplan apply
echo "OK"
