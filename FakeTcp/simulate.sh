#!/bin/bash

function setup_network() {
  echo "Setting up network simulation"
  sudo tc qdisc add dev lo root netem delay "$1"ms loss "$2"% duplicate "$3"%
  sudo tc qdisc show dev lo
}

function reset_network() {
  echo "Resetting network simulation"
  sudo tc qdisc del dev lo root
}

case "$1" in
  "start")
    # Parameters: delay_ms loss_percent duplication_percent
    setup_network "${2:-100}" "${3:-5}" "${4:-5}"
    ;;
  "stop")
    reset_network
    ;;
  *)
    echo "Usage: $0 start [delay_ms] [loss_percent] [duplicate_percent]"
    echo "       $0 stop"
    ;;
esac