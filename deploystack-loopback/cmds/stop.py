
def build_stop_parser(subparsers):

    parser = subparsers.add_parser(
        "stop",
        help="Stop a loopback resource"
    )

    parser.add_argument(
        "resource",
        choices=["cinder", "manila", "all"],
        default="all",
        help="Resource to stop"
    )

    parser.set_defaults(func=stop)

    return parser

def stop(args):
    print("stop")