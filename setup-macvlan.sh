#!/bin/bash

# This script sets up a macvlan network for the wake-up coach application
# and starts the container.

# Configuration - EDIT THESE VALUES
NETWORK_INTERFACE="eth0"  # Change to your network interface (e.g., eth0, ens33, etc.)
SUBNET="192.168.0.0/24"  # Change to your network subnet
GATEWAY="192.168.0.1"    # Change to your network gateway
IP_RANGE="192.168.0.100/29"  # Assign a specific IP range for the container
CONTAINER_IP="192.168.0.100"  # Specific IP for the container

# Create the macvlan network if it doesn't exist
echo "Creating macvlan network..."
docker network create -d macvlan \
  --subnet=$SUBNET \
  --gateway=$GATEWAY \
  -o parent=$NETWORK_INTERFACE \
  wakeup_network || echo "Network already exists"

# Update docker-compose.yml with the correct network interface
echo "Updating docker-compose.yml..."
sed -i "s/parent: eth0/parent: $NETWORK_INTERFACE/g" docker-compose.yml
sed -i "s/subnet: 192.168.0.0\/24/subnet: $SUBNET/g" docker-compose.yml
sed -i "s/gateway: 192.168.0.1/gateway: $GATEWAY/g" docker-compose.yml
sed -i "s/ip_range: 192.168.0.100\/29/ip_range: $IP_RANGE/g" docker-compose.yml

# Create or update .env file
echo "Creating .env file..."
cat > .env << EOL
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

# Application Configuration
PHONE_NUMBER=your_phone_number_here
WAKE_UP_TIME=06:00
SERVER_IP=$CONTAINER_IP
PORT=8000
EXTERNAL_PORT=8765
BASE_URL=http://$CONTAINER_IP:8765

# Timezone
TZ=America/New_York
EOL

echo "Please edit the .env file with your actual credentials."

# Build and start the container
echo "Building and starting the container..."
docker-compose build
docker-compose up -d

echo "Setup complete! The wake-up coach is now running on $CONTAINER_IP:8765"
echo "Please set up port forwarding on your router to forward port 8765 to $CONTAINER_IP:8000"
echo "Then update the BASE_URL in the .env file with your public IP address" 