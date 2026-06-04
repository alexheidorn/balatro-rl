# BalatrAI
### Balatro Reinforcement Learning Agent

A reinforcement learning environment and AI training framework for **Balatro**, built using a custom Lua mod and Python-based training pipeline. Originally forked from https://github.com/angelvalentin80/balatro-rl

## Overview
The project enables an AI agent to autonomously play Balatro by extracting game state information directly from the game engine and communicating with an external training process through inter-process communication (IPC).

## Features

* Real-time game state extraction from Balatro
* Bidirectional communication between Lua and Python
* Automated gameplay execution
* Reinforcement learning environment for agent training
* Debug visualization and logging tools
* Support for large-scale data collection and experimentation

## Motivation

Balatro presents an interesting challenge for reinforcement learning due to its combination of:

* Deck-building mechanics
* Randomized game states
* Long-term strategic planning
* Complex decision trees
* High reward variance

The goal of this project is to create a framework that allows AI agents to learn effective strategies through repeated gameplay rather than hard-coded heuristics.

## Architecture

```text
┌─────────────────┐
│     Balatro     │
│    (Lua Mod)    │
└────────┬────────┘
         │
         │ Game State
         ▼
┌─────────────────┐
│ Named Pipes IPC │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Python Training │
│    Environment  │
└────────┬────────┘
         │
         │ Actions
         ▼
┌─────────────────┐
│     Balatro     │
└─────────────────┘
```

### Lua Side

The Lua mod is responsible for:

* Monitoring game state
* Serializing observations
* Executing AI-selected actions
* Providing debugging information
* Synchronizing communication with the training environment

### Python Side

The Python training environment handles:

* State processing
* Reward calculation
* Agent training
* Experiment tracking
* Data collection and analysis

## Technical Challenges

### Inter-Process Communication

Balatro does not provide a native reinforcement learning API.

To bridge the game and the training environment, this project uses named pipes for communication between:

* Lua running inside Balatro
* External Python processes

This allows game state observations and agent actions to be exchanged in real time.

### Synchronization

One of the primary challenges was ensuring reliable synchronization between:

* Game frames
* AI decisions
* IPC messaging

Special care was taken to prevent:

* Deadlocks
* Race conditions
* Stale state information
* Invalid action execution

### Cross-Platform Support

Development involved debugging communication behavior across:

* Windows
* Linux
* Proton/Wine environments

This required handling differences in pipe creation, permissions, and process behavior.

## Future Goals

* PPO implementation
* Parallel environment support
* Distributed training
* State compression and optimization
* Advanced reward shaping
* Performance benchmarking against human players

## Technologies Used

* Lua
* Python
* Balatro Modding API
* Named Pipes (IPC)
* Reinforcement Learning
* Git

## Lessons Learned

This project provided hands-on experience with:

* Reinforcement learning system design
* Game engine integration
* Inter-process communication
* Systems debugging
* Cross-platform development
* Serialization and state management

## Disclaimer

Balatro is the property of its respective creators. This project is an educational and experimental integration intended for research and learning purposes.
