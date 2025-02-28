#!/bin/bash

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "tmux is not installed. Please install it first."
    exit 1
fi

# Create a new tmux session
tmux new-session -d -s life_narrative_explorer

# Split the window horizontally
tmux split-window -h -t life_narrative_explorer

# Run backend in the left pane
tmux send-keys -t life_narrative_explorer:0.0 "cd backend && . venv/bin/activate && echo 'Starting backend server...' && uvicorn main:app --reload" C-m

# Run frontend in the right pane
tmux send-keys -t life_narrative_explorer:0.1 "cd frontend && echo 'Starting frontend server...' && npm run dev" C-m

# Attach to the tmux session
tmux attach-session -t life_narrative_explorer

# When the tmux session ends, make sure to clean up
tmux kill-session -t life_narrative_explorer 2>/dev/null