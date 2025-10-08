import sys
import socket
import threading 
import mimetypes # Used to guess file types, but we'll override for the project specifications
import json
import time
import random
import string
import queue


# Server Configuration
HOST = '127.0.0.1'  # Run on localhost by default 
PORT = 8080         # Default port is 8080 
MAX_THREADS = 10    # Default maximum number of worker threads.
MAX_QUEUE_SIZE = 50

# Override default settings with command-line arguments if provided.
if len(sys.argv) > 1:
    PORT = int(sys.argv[1]) # First argument specifies the port.
if len(sys.argv) > 2:
    HOST = sys.argv[2]      # Second argument specifies the host.
if len(sys.argv) > 3:
    MAX_THREADS = int(sys.argv[3])  # Third argument specifies the max threads.

# --- GLOBAL SERVER SOCKET SETUP ---   

# Create a thread-safe queue to hold incoming client connections.
connection_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)

# Create a TCP socket for the server.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Bind the socket to the configured host and port.
server_socket.bind((HOST, PORT))
# Start listening for incoming connections with a queue size of 50.
server_socket.listen(50)

def worker(thread_id):
    """
    The target function for each worker thread.
    Waits for a connection from the queue and handles it.
    """
    while True:
        # Get a client socket from the queue. This call will block until a connection is available.
        client_socket = connection_queue.get()
        if client_socket is None:
            # A way to stop the thread if needed (optional).
            break

        current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
        print(f"[{current_time}] Connection dequeued, assigned to Thread-{thread_id}") 
        
        # Handle the client's request.
        handle_connection(client_socket, thread_id)
        
        # Mark the task as done.
        connection_queue.task_done()

def main():
    """
    Main function to set up the thread pool and accept client connections.
    """
    current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    print(f"[{current_time}] HTTP Server started on http://{HOST}:{PORT}") 
    print(f"[{current_time}] Thread pool size: {MAX_THREADS}") 
    print(f"[{current_time}] Serving files from 'resources' directory") 
    print(f"[{current_time}] Press Ctrl+C to stop the server") 

    # Create and start the fixed pool of worker threads.
    for i in range(MAX_THREADS):
        thread_id = i + 1
        thread = threading.Thread(target=worker, args=(thread_id,))
        thread.daemon = True  # Allows main thread to exit even if workers are blocking
        thread.start()

    # Main loop to accept new connections and put them in the queue.
    while True:
        client_socket, client_address = server_socket.accept()
        current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
        print(f"[{current_time}] Connection from {client_address[0]}:{client_address[1]}") 
        
        try:
            # Use non-blocking put to add to the queue.
            connection_queue.put_nowait(client_socket)
            print(f"[{current_time}] Connection added to queue.") #
        except queue.Full:
            # If the queue is full, the server is saturated.
            print(f"[{current_time}] Warning: Thread pool saturated, queuing connection") #
            print(f"[{current_time}] Rejecting connection from {client_address[0]}:{client_address[1]}")
            # Send a 503 Service Unavailable response.
            send_error(client_socket, 503, "Service Unavailable", keep_alive=False, extra_headers={"Retry-After": "10"})
            client_socket.close()


def handle_connection(client_socket, thread_id):
    """
    Handles the entire lifecycle of a client connection, now with robust error handling.
    """
    request_count = 0
    try:
        while request_count < 100:
            should_keep_alive = False # Default to closing connection
            try:
                client_socket.settimeout(30.0)
                request_data = client_socket.recv(8192).decode('utf-8')
                if not request_data:
                    break
                
                request_count += 1
                
                # --- Begin Per-Request Processing ---
                headers_part, body_part = request_data.split('\r\n\r\n', 1)
                first_line = headers_part.split('\r\n')[0]
                method, path, http_version = first_line.split(' ', 2)
                
                headers = {key.lower(): value for key, value in (line.split(': ', 1) for line in headers_part.split('\r\n')[1:] if ': ' in line)}

                # --- Decide Keep-Alive ---
                connection_header = headers.get('connection', '').lower()
                if http_version.endswith('/1.1') and connection_header != 'close':
                    should_keep_alive = True
                elif http_version.endswith('/1.0') and connection_header == 'keep-alive':
                    should_keep_alive = True
                
                if request_count >= 100: # Enforce max requests
                    should_keep_alive = False

                # --- Security and Routing ---
                server_host_address = f"{HOST}:{PORT}"
                if 'host' not in headers:
                    send_error(client_socket, 400, "Bad Request", should_keep_alive)
                    if not should_keep_alive: break
                    else: continue
                if headers['host'] != server_host_address:
                    send_error(client_socket, 403, "Forbidden", should_keep_alive)
                    if not should_keep_alive: break
                    else: continue
                
                # (Logging for request can go here)

                if method == 'GET':
                    serve_get_request(client_socket, path, thread_id, should_keep_alive)
                elif method == 'POST':
                    serve_post_request(client_socket, headers, body_part, thread_id, should_keep_alive)
                else:
                    send_error(client_socket, 405, "Method Not Allowed", should_keep_alive)
                
                if not should_keep_alive:
                    break

            except socket.timeout:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Thread-{thread_id}] Idle connection timed out.")
                break
            except Exception as e:
                # Catch any unexpected error during request processing.
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Thread-{thread_id}] Unhandled error during request: {e}")
                send_error(client_socket, 500, "Internal Server Error", keep_alive=False) #
                break # Always close a connection that caused a 500 error.

    except Exception as e:
        # Catch errors outside the request loop (e.g., during socket setup).
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Thread-{thread_id}] Critical error in connection handler: {e}")
    finally:
        client_socket.close()

def serve_get_request(client_socket, path, thread_id, keep_alive):
    """Handles GET requests by serving local files."""
    if path == '/':
        path = '/index.html' #

    # Security: Prevent path traversal attacks.
    if '..' in path:
        send_error(client_socket, 403, "Forbidden", keep_alive=False) #
        return

    filepath = f"resources{path}"
    filename = path.split('/')[-1]

    try:
        # Open and read the requested file in binary mode.
        with open(filepath, 'rb') as f: #
            content = f.read()

        # Determine the correct Content-Type.
        if filepath.endswith(".html"):
            content_type = "text/html; charset=utf-8" #
        elif filepath.endswith((".txt", ".png", ".jpg", ".jpeg")):
            content_type = "application/octet-stream" #
        else:
            send_error(client_socket, 415, "Unsupported Media Type", keep_alive=False) #
            return

        # Construct the HTTP response headers.
        current_date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        response_headers = f"HTTP/1.1 200 OK\r\n" #
        response_headers += f"Content-Type: {content_type}\r\n" #
        response_headers += f"Content-Length: {len(content)}\r\n" #
        response_headers += f"Date: {current_date}\r\n" #
        response_headers += "Server: My Python HTTP Server\r\n" #

        # Add Content-Disposition for binary downloads.
        if content_type == "application/octet-stream":
            response_headers += f'Content-Disposition: attachment; filename="{filename}"\r\n' #

        # Add conditional Connection and Keep-Alive headers.
        if keep_alive:
            response_headers += "Connection: keep-alive\r\n" #
            response_headers += "Keep-Alive: timeout=30, max=100\r\n\r\n" #
        else:
            response_headers += "Connection: close\r\n\r\n" #

        # Send the complete response to the client.
        client_socket.sendall(response_headers.encode('utf-8') + content)

    except FileNotFoundError:
        # If the file doesn't exist, send a 404 error.
        send_error(client_socket, 404, "Not Found", keep_alive=False) 

def serve_post_request(client_socket, headers, body_part, thread_id, keep_alive):
    """Handles POST requests by saving uploaded JSON data to a file."""
    # Enforce that the uploaded content must be JSON.
    if not headers.get('content-type', '').startswith('application/json'): #
        send_error(client_socket, 415, "Unsupported Media Type", keep_alive=False) #
        return

    try:
        # Try to parse the JSON data from the request body.
        json_data = json.loads(body_part) #
    except json.JSONDecodeError:
        # If JSON is malformed, send a 400 error.
        send_error(client_socket, 400, "Bad Request", keep_alive=False) #
        return

    # Generate a unique filename for the uploaded data.
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    filename = f"upload_{timestamp}_{random_id}.json" #
    filepath = f"resources/uploads/{filename}"

    try:
        # Write the received JSON data to the new file.
        with open(filepath, 'w') as f: #
            json.dump(json_data, f, indent=4) #

        # Prepare a successful 201 Created response body.
        response_body_dict = {
            "status": "success", #
            "message": "File created successfully", #
            "filepath": f"/uploads/{filename}" #
        }
        response_body = json.dumps(response_body_dict)

        # Construct the 201 Created response headers.
        current_date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        response_headers = f"HTTP/1.1 201 Created\r\n" #
        response_headers += "Content-Type: application/json\r\n" #
        response_headers += f"Content-Length: {len(response_body)}\r\n" #
        response_headers += f"Date: {current_date}\r\n" #
        response_headers += "Server: My Python HTTP Server\r\n" #

        # Add conditional Connection and Keep-Alive headers.
        if keep_alive:
            response_headers += "Connection: keep-alive\r\n" #
            response_headers += "Keep-Alive: timeout=30, max=100\r\n\r\n" #
        else:
            response_headers += "Connection: close\r\n\r\n" #

        # Send the complete response to the client.
        client_socket.sendall(response_headers.encode('utf-8') + response_body.encode('utf-8'))

    except Exception as e:
        # Handle potential file system errors.
        print(f"[Thread-{thread_id}] Error creating file: {e}")
        send_error(client_socket, 500, "Internal Server Error", keep_alive=False) #

def send_error(client_socket, status_code, status_message, keep_alive, extra_headers=None):
    """A helper function to send formatted HTTP error responses."""
    response_body = f"<html><body><h1>{status_code} {status_message}</h1></body></html>"
    response_headers = f"HTTP/1.1 {status_code} {status_message}\r\n"
    response_headers += "Content-Type: text/html; charset=utf-8\r\n"
    response_headers += f"Content-Length: {len(response_body)}\r\n"
    
    # Add extra headers if provided (for 503 Retry-After)
    if extra_headers:
        for key, value in extra_headers.items():
            response_headers += f"{key}: {value}\r\n"

    # Conditional Connection Headers
    if keep_alive:
        response_headers += "Connection: keep-alive\r\n"
        response_headers += "Keep-Alive: timeout=30, max=100\r\n\r\n"
    else:
        response_headers += "Connection: close\r\n\r\n"
        
    client_socket.sendall(response_headers.encode('utf-8') + response_body.encode('utf-8'))

# This block ensures the main() function is called only when the script is executed directly.
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Allows for a graceful shutdown of the server with Ctrl+C.
        print("\nServer shutting down...")
        server_socket.close()
