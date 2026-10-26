#!/bin/bash
# WireGuard setup for Houston phone-remote-control (fresh VPS only; idempotent-ish).
# Generates ALL keys at runtime — never echo them. Safe to run via: sudo bash wg_setup.sh
set -e
umask 077

SERVER_PRIV=$(wg genkey); SERVER_PUB=$(echo "$SERVER_PRIV" | wg pubkey)
CLIENT_PRIV=$(wg genkey); CLIENT_PUB=$(echo "$CLIENT_PRIV" | wg pubkey)
PSK=$(wg genpsk)

mkdir -p /etc/wireguard

cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = $SERVER_PRIV

[Peer]
PublicKey = $CLIENT_PUB
PresharedKey = $PSK
AllowedIPs = 10.66.66.2/32
EOF

cat > /etc/wireguard/phone0.conf <<EOF
[Interface]
PrivateKey = $CLIENT_PRIV
Address = 10.66.66.2/32

[Peer]
PublicKey = $SERVER_PUB
PresharedKey = $PSK
Endpoint = YOUR_VPS_PUBLIC_IP:51820
AllowedIPs = 10.66.66.0/24
PersistentKeepalive = 25
EOF

chmod 600 /etc/wireguard/wg0.conf /etc/wireguard/phone0.conf

# deliver client config + QR to the ssh user (for emailing to the phone owner)
install -m 600 -o "$USER" -g "$USER" /etc/wireguard/phone0.conf $HOME/wg-phone.conf
qrencode -t png -o $HOME/wg-phone.png < /etc/wireguard/phone0.conf
chown "$USER":"$USER" $HOME/wg-phone.png && chmod 600 $HOME/wg-phone.png

systemctl enable --now wg-quick@wg0
echo "=== wg show ===" && wg show
echo "SETUP_OK — remember: sudo ufw allow 51820/udp"
