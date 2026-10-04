"""Command line for the data pipeline. Run from the repo root:

  python3 -m pipeline build           catalog, measure, validate, similarity, public
  python3 -m pipeline catalog         add records for new images, refresh file facts
  python3 -m pipeline measure         colour and structure features, thumbnails (--force)
  python3 -m pipeline validate        check records against vocabulary (--adopt)
  python3 -m pipeline similarity      neighbours and 2D layout
  python3 -m pipeline public          write data/public/ for the website
  python3 -m pipeline apply FILE...   merge described blocks from batch files
  python3 -m pipeline embed           optional CLIP embeddings (needs torch)
  python3 -m pipeline quarto-import   legacy import from the old Quarto pages
"""
import sys

from . import apply, catalog, embed, measure, public, quarto_import, similarity, validate

COMMANDS = {
    "catalog": catalog.main,
    "measure": measure.main,
    "validate": validate.main,
    "similarity": similarity.main,
    "public": public.main,
    "apply": apply.main,
    "embed": embed.main,
    "quarto-import": quarto_import.main,
}


def build(argv):
    for name in ("catalog", "measure", "validate", "similarity", "public"):
        print(f"== {name}")
        code = COMMANDS[name]([a for a in argv if name != "validate" or a == "--adopt"])
        if code:
            if name == "validate":
                print("validate reported problems; fix them or run `pipeline validate --adopt` to accept new tags")
            return code
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "build":
        return build(argv)
    if cmd not in COMMANDS:
        print(f"unknown command {cmd}\n{__doc__}")
        return 1
    return COMMANDS[cmd](argv) or 0


sys.exit(main())
