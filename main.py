"""
ErgoGuard AI — Main Entry Point
Launches the high-performance AI video processing and safety telemetry pipeline.
"""
import sys

# Ensure stdout and stderr flush immediately on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

from ai.video_processor import main

if __name__ == "__main__":
    main()

