import sys

from meeting_assistant.cli import app

if __name__ == "__main__":
    app(args=["devices", *sys.argv[1:]])
