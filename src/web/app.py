import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import os
import logging
from datetime import datetime
import json
import sys
import threading
import queue
import copy

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.main import merge_metadata

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Queue for storing logs
log_queue = queue.Queue()

class WebSocketLogHandler(logging.Handler):
    """Custom log handler that sends logs to WebSocket clients"""
    def emit(self, record):
        try:
            # Create a copy of the record to avoid modifying the original
            record_copy = copy.copy(record)
            # Format the log message
            log_entry = self.format(record_copy)
            # Send to WebSocket clients
            socketio.emit('log_update', {'log': log_entry}, namespace='/')
        except Exception as e:
            logger.error(f"Error in WebSocketLogHandler: {str(e)}")
            self.handleError(record)

# Add WebSocket handler to logger
web_logger = logging.getLogger('web_logger')
web_logger.setLevel(logging.INFO)
web_handler = WebSocketLogHandler()
web_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s: %(message)s', datefmt='%Y-%m-%d_%H:%M:%S'))
web_logger.addHandler(web_handler)

# Create a custom logging filter to duplicate logs
class LogDuplicator(logging.Filter):
    def filter(self, record):
        # Create a copy of the record for the web logger
        web_logger.handle(record)
        return True

# Add the filter to the main logger
logger.addFilter(LogDuplicator())

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    emit('log_update', {'log': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

@app.route('/')
def index():
    # Test log when page is loaded
    logger.info("Web interface loaded")
    return render_template('index.html')

@app.route('/browse_directory', methods=['POST'])
def browse_directory():
    data = request.json
    current_path = data.get('path', '/')
    
    try:
        # Ensure the path exists and is a directory
        if not os.path.exists(current_path) or not os.path.isdir(current_path):
            return jsonify({'error': 'Invalid directory path'}), 400

        # Get parent directory
        parent_dir = os.path.dirname(current_path) if current_path != '/' else None

        # List directories and files
        items = []
        for item in os.listdir(current_path):
            full_path = os.path.join(current_path, item)
            try:
                is_dir = os.path.isdir(full_path)
                # Skip hidden files and directories
                if not item.startswith('.'):
                    items.append({
                        'name': item,
                        'path': full_path,
                        'is_dir': is_dir
                    })
            except PermissionError:
                continue

        # Sort: directories first, then files, both alphabetically
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

        return jsonify({
            'current_path': current_path,
            'parent_dir': parent_dir,
            'items': items
        })

    except Exception as e:
        logger.error(f"Error browsing directory: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/select_directory', methods=['POST'])
def select_directory():
    directory = request.json.get('directory')
    if not os.path.exists(directory):
        return jsonify({'error': 'Directory does not exist'}), 400
    return jsonify({'success': True, 'path': directory})

def background_process(input_dir, output_dir, dry_run, overwrite, log_level):
    try:
        def progress_callback(progress_data):
            try:
                socketio.emit('progress_update', progress_data, namespace='/')
                eventlet.sleep(0)  # Give Socket.IO a chance to send the message
            except Exception as e:
                logger.error(f"Error emitting progress update: {str(e)}")
            
        success = merge_metadata(input_dir, output_dir, dry_run, overwrite, progress_callback)
        try:
            socketio.emit('process_complete', {'success': success}, namespace='/')
        except Exception as e:
            print(f"Error emitting process complete: {str(e)}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Processing error: {error_msg}")
        try:
            socketio.emit('process_complete', {'success': False, 'error': error_msg}, namespace='/')
        except Exception as e:
            logger.error(f"Error emitting process error: {str(e)}")

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    input_dir = data.get('inputDir')
    output_dir = data.get('outputDir')
    log_level = data.get('logLevel', 'INFO')
    dry_run = data.get('dryRun', False)
    overwrite = data.get('overwriteIfExists', False)

    # Validate directories
    if not os.path.exists(input_dir):
        return jsonify({'error': 'Input directory does not exist'}), 400
    if input_dir == output_dir:
        return jsonify({'error': 'Input and output directories must be different'}), 400

    # Set log level for both loggers
    logger.setLevel(getattr(logging, log_level))
    web_logger.setLevel(getattr(logging, log_level))

    # Start processing in a background task
    eventlet.spawn(background_process, input_dir, output_dir, dry_run, overwrite, log_level)
    return jsonify({'message': 'Processing started'})

@app.route('/download_logs')
def download_logs():
    # Create a temporary file with all logs
    log_file = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(log_file, 'w') as f:
        while not log_queue.empty():
            f.write(log_queue.get() + '\n')
    
    return send_file(log_file, as_attachment=True)

if __name__ == '__main__':
    # Test log when server starts
    logger.info("Server starting")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 