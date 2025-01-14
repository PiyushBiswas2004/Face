from waitress import serve
from attendance_app import app
import webbrowser
import os

if __name__ == "__main__":
    # Initialize the database
    from attendance_app import init_db
    init_db()
    
    # Print serving message
    host = '0.0.0.0'
    port = 8000
    print(f"Starting server on http://localhost:{port}")
    
    # Open browser automatically
    webbrowser.open(f'http://localhost:{port}')
    
    # Start the server
    serve(app, host=host, port=port, threads=4)