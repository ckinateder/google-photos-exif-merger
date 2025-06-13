import os
import sys
import argparse

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.web.app import app, socketio

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the web app')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the app on')
    args = parser.parse_args()
    socketio.run(app, host='0.0.0.0', port=args.port, debug=True) 