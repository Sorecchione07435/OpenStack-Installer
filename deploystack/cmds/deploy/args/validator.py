def validate_deploy_args(parser, args):

    if args.install_manila == "no":

        provided = [
            args.manila_lvm_physical_volume is not None,
            args.manila_lvm_image_size_in_gb is not None,
            args.manila_backend is not None,
            args.manila_share_protocols is not None,
        ]

        if any(provided):
            parser.error(
                "Manila options require --install-manila yes"
            )

    if args.install_cinder == "no":

        provided = [
            args.cinder_physical_volume is not None,
            args.cinder_lvm_image_size_in_gb != 5,
        ]

        if any(provided):
            parser.error(
                "Cinder options require --install-cinder yes"
            )