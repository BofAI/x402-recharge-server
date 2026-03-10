#!/bin/bash

# Startup wrapper. Registration is intentionally handled by scripts/register_8004.py
# and scripts/update_8004.py.
exec "$(cd "$(dirname "$0")" && pwd)/scripts/start_agent.sh"
