#!/bin/bash

LOOP_DEV="{lvm_loop_dev}"
IMAGE_FILE="{lvm_image_file_path}"
VG_NAME="{VG_NAME}"

if [ -z "$PHYSICAL_VOLUME" ]; then

    if [ ! -f "$IMAGE_FILE" ]; then
        echo "ERROR: LVM image file not found: $IMAGE_FILE"
        exit 1
    fi

    if ! /sbin/losetup "$LOOP_DEV" 2>/dev/null | grep -q "$IMAGE_FILE"; then
        
        if /sbin/losetup "$LOOP_DEV" >/dev/null 2>&1; then
            echo "Detaching old loop device $LOOP_DEV"
            /sbin/losetup -d "$LOOP_DEV"
        fi

        echo "Attaching $IMAGE_FILE to $LOOP_DEV"
        /sbin/losetup "$LOOP_DEV" "$IMAGE_FILE"
    fi
fi

/sbin/vgchange -ay "$VG_NAME"