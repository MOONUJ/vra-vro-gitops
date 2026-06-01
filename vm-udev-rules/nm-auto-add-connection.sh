#!/bin/bash
INTERFACE="$1"

sleep 5

if ! nmcli connection show "$INTERFACE" &>/dev/null; then
    nmcli connection add \
            type ethernet \
            ifname "$INTERFACE" \
            con-name "$INTERFACE" \
            autoconnect yes \
            ipv4.method auto \
            ipv6.method auto
    
    echo "$(date): Added connection for $INTERFACE" >> /var/log/nm-auto-add.log
fi

exit 0