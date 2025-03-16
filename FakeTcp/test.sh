#!/bin/bash
# filepath: /home/phuwit/Programming/KMITL-ComputerNetworks/FakeTcp/test_network.sh

set -e

# Configuration
TEST_FILE="${1:-sample.txt}"  # Default to sample.txt if no file provided
SERVER_IP="127.0.0.1"
SERVER_PORT="12345"
OUTPUT_DIR="test_results"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to apply network conditions
setup_network() {
  echo "Setting up network: delay=${1}ms loss=${2}% duplicate=${3}% reorder=${4}%"
  sudo tc qdisc del dev lo root 2>/dev/null || true
  if [ "$4" -gt 0 ]; then
    # With reordering
    sudo tc qdisc add dev lo root netem delay "$1"ms reorder "$4"% loss "$2"% duplicate "$3"%
  else
    # Without reordering
    sudo tc qdisc add dev lo root netem delay "$1"ms loss "$2"% duplicate "$3"%
  fi
  sudo tc qdisc show dev lo
}

# Function to reset network
reset_network() {
  echo "Resetting network simulation"
  sudo tc qdisc del dev lo root 2>/dev/null || true
}

# Function to run a test case
run_test() {
  local test_name="$1"
  local delay_ms="$2"
  local loss="$3"
  local duplicate="$4"
  local reorder="$5"
  local output_file="${OUTPUT_DIR}/${test_name}_$(basename "$TEST_FILE")"

  echo "===================================================="
  echo "Running test: $test_name"
  echo "===================================================="

  # Setup network conditions
  setup_network "$delay_ms" "$loss" "$duplicate" "$reorder"

  # Start server in background
  python3 urft_server.py "$SERVER_IP" "$SERVER_PORT" &
  server_pid=$!

  # Give server time to start
  sleep 1

  # Start client
  echo "Starting client..."
  python3 urft_client.py "$TEST_FILE" "$SERVER_IP" "$SERVER_PORT"

  # Wait for server to complete
  wait $server_pid

  # Verify file integrity
  echo "Verifying file integrity..."
  original_md5=$(md5sum "$TEST_FILE" | awk '{print $1}')
  received_md5=$(md5sum "$(basename "$TEST_FILE")" | awk '{print $1}')

  if [ "$original_md5" = "$received_md5" ]; then
    echo "✅ File integrity check PASSED"
  else
    echo "❌ File integrity check FAILED"
    echo "Original MD5: $original_md5"
    echo "Received MD5: $received_md5"
  fi

  rm "$(basename "$TEST_FILE")"

  # Reset network
  reset_network

  echo ""
}

# Check if test file exists
if [ ! -f "$TEST_FILE" ]; then
  echo "Error: Test file '$TEST_FILE' not found"
  exit 1
fi

echo "Starting tests with file: $TEST_FILE"

# Create a simple test file if not specified
if [ "$TEST_FILE" = "sample.txt" ] && [ ! -f "$TEST_FILE" ]; then
  echo "Creating sample test file..."
  dd if=/dev/urandom of="$TEST_FILE" bs=1M count=5
fi

# Run test cases
run_test "1_10ms_rtt" 5 0 0 0                  # 10ms RTT (5ms one-way)
run_test "2_10ms_rtt_2pct_duplication" 5 0 2 0 # 10ms RTT + 2% duplication
run_test "3_10ms_rtt_2pct_loss" 5 2 0 0        # 10ms RTT + 2% loss
run_test "4_10ms_rtt_5pct_duplication" 5 0 5 0 # 10ms RTT + 5% duplication
run_test "5_10ms_rtt_5pct_loss" 5 5 0 0        # 10ms RTT + 5% loss
run_test "6_250ms_rtt" 125 0 0 0               # 250ms RTT (125ms one-way)
run_test "7_250ms_rtt_2pct_reordering" 125 0 0 2 # 250ms RTT + 2% reordering

echo "All tests completed. Results saved in $OUTPUT_DIR/"