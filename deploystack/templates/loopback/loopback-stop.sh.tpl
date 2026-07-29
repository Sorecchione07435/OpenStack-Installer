#!/bin/bash

VG_NAME="{VG_NAME}"
LOOP_DEV="{lvm_loop_dev}"
IMAGE_FILE="{lvm_image_file_path}"

/sbin/vgchange -an "$VG_NAME"

if [ -z "$PHYSICAL_VOLUME" ]; then
    if /sbin/losetup "$LOOP_DEV" 2>/dev/null | grep -q "$IMAGE_FILE"; then
        /sbin/losetup -d "$LOOP_DEV"
    fi
fi

exit 0