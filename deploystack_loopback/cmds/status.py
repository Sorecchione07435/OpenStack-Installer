def build_status_parser(subparsers):

    parser = subparsers.add_parser(
        "status",
        help="Show loopback resources status"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila"],
        default=None,
        help="Resource to show"
    )

    parser.set_defaults(func=status)

    return parser

def status(args):
    print("status")