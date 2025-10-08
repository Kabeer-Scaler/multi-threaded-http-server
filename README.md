# Multi-Threaded HTTP Server
This project is a multi-threaded HTTP server built from scratch in Python using low-level socket programming. It is designed to handle multiple concurrent clients, serve static and binary files, process POST requests with JSON data, and implement advanced features like a thread pool and persistent connections.

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
