#!/bin/bash

# Source the global .gigi-env file to load all environment variables
if [ -f "$HOME/.gigi-env" ]; then
  source "$HOME/.gigi-env"
else
  echo "Error: ~/.gigi-env not found!"
  exit 1
fi

# Execute the Telegram bot Python script
exec /usr/bin/python3 "/Users/shulmeister/mac-mini-apps/careassist-unified/gigi/telegram_bot.py"
