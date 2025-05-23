# Run the setup script first
echo "Running setup script..."
python3 setup.py

# Check if port 5500 is already in use
echo "Checking if API port is in use..."
if lsof -i:5500 > /dev/null; then
    echo "Port 5500 is already in use. Stopping the existing process..."
    # Find the PID of the process using port 5500
    PID=$(lsof -t -i:5500)
    if [ ! -z "$PID" ]; then
        # Kill the process
        kill -9 $PID
        echo "Killed process with PID: $PID"
        # Wait a moment for the port to be released
        sleep 2
    fi
fi

# Start the Flask API server in the background
echo "Starting the Flask API server..."
python3 api_server.py &
API_PID=$!
echo "API server running with PID: $API_PID"

# Wait for the API server to start
echo "Waiting for API server to be ready..."
sleep 3

# Change to the frontend directory and start the Next.js app
echo "Starting the Next.js frontend..."
cd frontend
npm run dev

# When the frontend is stopped, kill the API server
echo "Stopping the API server..."
kill $API_PID 