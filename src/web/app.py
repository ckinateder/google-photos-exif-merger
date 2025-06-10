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
import signal

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.main import merge_metadata

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Global variable to store the current processing task
current_task = None

class WebSocketLogHandler(logging.Handler):
    """Custom log handler that sends logs to WebSocket clients"""
    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s: %(message)s', datefmt='%Y-%m-%d_%H:%M:%S'))
        # Store logs for download
        self.log_queue = queue.Queue()

    def emit(self, record):
        try:
            # Create a copy of the record to avoid modifying the original
            record_copy = copy.copy(record)
            # Format the log message
            log_entry = self.format(record_copy)
            # Store in queue for download
            self.log_queue.put(log_entry)
            # Send to WebSocket clients with level information
            socketio.emit('log_update', {
                'log': log_entry,
                'level': record_copy.levelname,
                'timestamp': datetime.fromtimestamp(record_copy.created).strftime('%Y-%m-%d_%H:%M:%S')
            }, namespace='/')
        except Exception as e:
            logger.error(f"Error in WebSocketLogHandler: {str(e)}")
            self.handleError(record)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S'
)

# Create and configure the WebSocket handler
websocket_handler = WebSocketLogHandler()
websocket_handler.setLevel(logging.DEBUG)  # Capture all levels

# Get the root logger and add our handler
root_logger = logging.getLogger()
root_logger.addHandler(websocket_handler)

# Get the logger for this module
logger = logging.getLogger(__name__)

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    emit('log_update', {'log': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

@app.route('/')
def index():
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
    global current_task
    current_task = eventlet.getcurrent()
    
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
            logger.error(f"Error emitting process complete: {str(e)}")
    except eventlet.greenlet.GreenletExit:
        logger.info("Processing aborted by user")
        try:
            socketio.emit('process_complete', {'success': False, 'error': 'Processing aborted by user'}, namespace='/')
        except Exception as e:
            logger.error(f"Error emitting process abort: {str(e)}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Processing error: {error_msg}")
        try:
            socketio.emit('process_complete', {'success': False, 'error': error_msg}, namespace='/')
        except Exception as e:
            logger.error(f"Error emitting process error: {str(e)}")
    finally:
        current_task = None

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
    root_logger.setLevel(getattr(logging, log_level))

    # Start processing in a background task
    eventlet.spawn(background_process, input_dir, output_dir, dry_run, overwrite, log_level)
    return jsonify({'message': 'Processing started'})

@app.route('/download_logs')
def download_logs():
    # Create a temporary file with all logs
    log_file = f"logs_{datetime.now().strftime('%Y%m%d_%H%M:%S')}.txt"
    with open(log_file, 'w') as f:
        while not websocket_handler.log_queue.empty():
            f.write(websocket_handler.log_queue.get() + '\n')
    
    return send_file(log_file, as_attachment=True)

@app.route('/abort', methods=['POST'])
def abort():
    global current_task
    if current_task is not None:
        try:
            current_task.kill()
            logger.info("Processing task aborted")
            return jsonify({'message': 'Processing aborted'})
        except Exception as e:
            logger.error(f"Error aborting task: {str(e)}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'message': 'No task running'})

if __name__ == '__main__':
    # Test log when server starts
    logger.info("Server starting")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 