# ShellLite Chess Engine and Lichess Bot

A chess engine built entirely in the ShellLite programming language, along with a Lichess Bot Bridge integration.

## Features

* Universal Chess Interface compliant engine loop
* Optimised search using Negamax with Alpha Beta Pruning and Transposition Table caching
* Tactical evaluation featuring Piece Square Tables and Delta Pruning
* Custom legal capture generator for quiescence search
* Lichess integration with automatic reconnection on stream disconnections

## Architecture

The system consists of two primary components.

1. The ShellLite Chess Engine: Written in ShellLite, implementing the board representation, move generation, and tactical search. It communicates using the standard Universal Chess Interface protocol.
2. The Lichess Bot Bridge: A multithreaded Python application that streams challenges and game events from Lichess, automatically spawning separate, isolated ShellLite engine processes to calculate and make moves for each game.

## Requirements

* Python 3.10 or higher
* Requests library
* ShellLite interpreter

## Installation and Setup

1. Clone this repository to your local machine.
2. Install the required Python dependencies:
   pip install shell-lite
   pip install requests
3. Copy the configuration template file:
   copy lichess_config.json.example lichess_config.json
4. Edit lichess_config.json and replace YOUR_LICHESS_BOT_TOKEN_HERE with your private Lichess Bot API token.

## Running the Engine Locally

To run and test the engine locally via the Universal Chess Interface CLI:

* On Windows, run the run_engine.bat file.
* On Linux or macOS, run:
  shl main.shl OR shl run main.shl

## Running the Lichess Bot

To start the bot and connect it to Lichess:

* On Windows, run the run_lichess.bat file.
* On Linux or macOS, run:
  python lichess_bot.py

ENJOY!

License: MIT
