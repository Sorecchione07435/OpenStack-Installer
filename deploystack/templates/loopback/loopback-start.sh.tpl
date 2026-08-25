#!/bin/bash

IMAGE_FILE="{lvm_image_file_path}"
VG_NAME="{VG_NAME}"
STATE_FILE="/var/lib/deploystack/loop_dev"

LVM_CONF="/etc/lvm/lvm.conf"

if [ -z "$PHYSICAL_VOLUME" ]; then

    if [ ! -f "$IMAGE_FILE" ]; then
        echo "ERROR: LVM image file not found: $IMAGE_FILE"
        exit 1
    fi

    mkdir -p "$(dirname "$STATE_FILE")"

    EXISTING_DEV=$(/sbin/losetup -j "$IMAGE_FILE" | cut -d: -f1)

    if [ -n "$EXISTING_DEV" ]; then
        LOOP_DEV="$EXISTING_DEV"
    else
        LOOP_DEV=$(/sbin/losetup -f)
        echo "Attaching $IMAGE_FILE to $LOOP_DEV"
        /sbin/losetup "$LOOP_DEV" "$IMAGE_FILE"
    fi

    echo "$LOOP_DEV" > "$STATE_FILE"
    
    sed -i -E "s|^\s*filter\s*=.*|    filter = [ \"a|^${LOOP_DEV}\$|\", \"r|.*|\" ]|" "$LVM_CONF"

    /sbin/pvscan --cache "$LOOP_DEV"
fi

/sbin/vgchange -ay "$VG_NAME"