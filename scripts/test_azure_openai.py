import sys

from meeting_assistant.cli import app

if __name__ == "__main__":
    app(args=["test-azure", *sys.argv[1:]])
