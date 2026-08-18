import sys

from meeting_assistant.cli import app

if __name__ == "__main__":
    app(args=["test-audio", *sys.argv[1:]])
