# Multi-Threaded HTTP Server
This project is a high-performance, multi-threaded HTTP server built from scratch in Python using low-level socket programming. It is designed to handle multiple concurrent clients, serve static and binary files, process POST requests with JSON data, and implement advanced features like a thread pool, persistent connections, and robust security checks, all according to the project specification.

## Features
- Concurrent Architecture: Implements a fixed-size thread pool to handle multiple simultaneous client connections efficiently.

- Persistent Connections: Supports Keep-Alive to serve multiple requests on a single connection, with a 30-second idle timeout and a 100-request limit.

- GET Request Handling:

1) Serves HTML files for in-browser rendering.

2) Serves binary files (images, text files) as attachments to trigger downloads.

- POST Request Handling:

1) Processes application/json content.

2) Creates new files on the server with the received JSON data.

- Robust Security:

1) Includes Path Traversal Protection to prevent access to unauthorized files.

2) Implements strict Host Header Validation on all requests.

- Comprehensive Error Handling: Correctly returns a wide range of HTTP status codes, including 4xx client errors and 5xx server errors (like 503 Service Unavailable when the server is overloaded).

- Configurable: Server host, port, and thread pool size can be configured via command-line arguments.

## Code Architecture and Functioning
This section explains the end-to-end functioning of the server, from startup to handling a single request.

### 1. Server Initialization
When server.py is executed, the following setup process occurs in the main thread:

- Configuration: The script parses command-line arguments (sys.argv) to set the HOST, PORT, and MAX_THREADS. If any are not provided, it uses safe default values.

- Socket Creation: A primary TCP socket is created, bound to the specified host and port, and put into listening mode with a backlog queue size of 50.

- Connection Queue: A thread-safe queue.Queue is created with a maximum size. This queue will act as a buffer, holding incoming client connections that are waiting for a worker thread to become available.

- Thread Pool Creation: The server initializes its thread pool by creating and starting a fixed number of worker threads (defined by MAX_THREADS). Each thread is set as a "daemon" so that it will not prevent the main program from exiting.

### 2. Concurrency Model: The Thread Pool
The server's concurrency model is built around a producer-consumer pattern:

- The Producer (Main Thread): The main thread's only job is to run an infinite loop calling server_socket.accept(). When a new client connects, this call unblocks, and the main thread attempts to place the new client socket onto the shared connection_queue using put_nowait().

- The Consumers (Worker Threads): Each worker thread runs a worker function in an infinite loop. The first thing they do is call connection_queue.get(). This is a blocking call, so the thread will sleep efficiently until a client socket appears in the queue. Once a socket is retrieved, the worker is considered "busy."

- Handling Overload (503 Error): If a new client connects while all worker threads are busy and the connection_queue is also full, the put_nowait() call in the main thread will raise a queue.Full exception. This is caught, and the server immediately sends a 503 Service Unavailable response to that new client and closes their connection, protecting the server from being overwhelmed.

### 3. Connection and Request Lifecycle
Once a worker thread retrieves a client socket from the queue, it calls the handle_connection function, which manages the entire lifecycle of that persistent connection.

- Keep-Alive Loop: The function enters a while loop that can run up to 100 times (the max request limit).

- Idle Timeout: At the start of each loop, a 30-second timeout is set on the client socket using socket.settimeout().

- Waiting for Data: The thread blocks on socket.recv(), waiting for the client to send a request. If the client remains idle for more than 30 seconds, a socket.timeout exception is raised, the loop is broken, and the connection is closed.

- Request Parsing: Once data is received, the raw HTTP request is parsed into its components: method, path, HTTP version, and headers (stored in a dictionary).

- Security Checks: The parsed request is immediately subjected to the Host Header validation check.

- Request Routing: Based on the request method, the server routes the request to the appropriate function:

i) serve_get_request: For GET requests, this function performs the Path Traversal security check. It then determines the file's Content-Type. If it's HTML, it prepares headers for rendering. If it's a binary file, it prepares Content-Type: application/octet-stream and Content-Disposition: attachment headers to force a download. It then reads the file from disk in binary mode and sends the complete HTTP response.

ii) serve_post_request: For POST requests, this function first validates that the Content-Type is application/json. It then parses the JSON body. If successful, it generates a unique filename, writes the JSON data to a new file in the resources/uploads/ directory, and sends a 201 Created response.

- Connection State: After a response is sent, the server inspects the client's Connection header and its own request counter to determine if it should continue the loop (for a keep-alive connection) or break the loop to close the connection.

- Cleanup: Once the loop is broken for any reason (timeout, client closed, request limit, or Connection: close header), the finally block ensures the client_socket is always closed.

## Build and Run Instructions

### Directory Structure
To run the server, the following directory structure must be in place:

project/
├── data.json
├── server.py
├── resources/
│   ├── index.html
│   ├── about.html
│   ├── sample.txt
│   ├── logo.png
│   ├── photo.jpg
│   ├── contact.html
│   ├── sample2.txt
│   ├── sample_image.png
│   ├── peacock_feather.jpg
│   └── uploads/

The uploads/ directory must exist but should be empty initially, as it is used to store files created via POST requests.

### Running the Server
Navigate to the project/ directory in your terminal and run the server using the following command:
python server.py 

## Description of Binary Transfer Implementation
The server is capable of handling GET requests for binary files (e.g., .png, .jpg, .txt) and serving them in a way that prompts the client's browser to download the file.

This is achieved through the following implementation details:


- Binary Read Mode: All files are opened and read in binary mode ('rb') to ensure that the data integrity is preserved during transfer.



- Content-Type Header: For binary transfers, the server sets the Content-Type header to application/octet-stream. This generic content type signals to the browser that it should not attempt to render the file.


- Content-Disposition Header: To explicitly trigger a download, the server includes the Content-Disposition: attachment; filename="[filename]" header in the response.

## Thread Pool Architecture Explanation
The server uses a thread pool architecture to handle multiple concurrent clients efficiently.


- Fixed-Size Thread Pool: At startup, the server creates a fixed number of worker threads, with the size determined by the MAX_THREADS configuration (defaulting to 10). These threads are long-lived and are reused for multiple connections.



- Connection Queue: A thread-safe queue is used to manage incoming client connections. When the main thread accepts a new connection, it places the client socket into this queue.


- Worker Threads: The worker threads continuously monitor the queue. When a connection becomes available, an idle worker thread retrieves it from the queue, handles the entire client connection (including any keep-alive requests), and then returns to the queue to wait for the next job.


- Synchronization: Thread safety is ensured by using Python's built-in queue.Queue, which handles all the necessary locking and synchronization internally to prevent race conditions.

## Security Measures Implemented
The server includes two critical security features as required:


- Path Traversal Protection: The server validates the path for all GET requests to prevent directory traversal attacks. It specifically blocks any request path containing .. and immediately returns a 403 Forbidden error to deny access to files outside the designated resources directory.



- Host Header Validation: The server inspects the Host header on every incoming request. It verifies that the header is present (returning 400 Bad Request if missing) and that its value matches the server's own address (returning 403 Forbidden if there is a mismatch).

## Known Limitations
The implementation adheres to all major functional, security, and advanced architecture requirements laid out in the project document. Minor logging features, such as a periodic "Thread pool status" message, are not implemented.
