#!/bin/bash

VG_NAME="{VG_NAME}"
IMAGE_FILE="{lvm_image_file_path}"
STATE_FILE="/var/lib/deploystack/loop_dev"

/sbin/vgchange -an "$VG_NAME"

if [ -z "$PHYSICAL_VOLUME" ]; then
    LOOP_DEV=$(/sbin/losetup -j "$IMAGE_FILE" | cut -d: -f1)
    if [ -n "$LOOP_DEV" ]; then
        /sbin/losetup -d "$LOOP_DEV"
    fi
    rm -f "$STATE_FILE"
fi

exit 0