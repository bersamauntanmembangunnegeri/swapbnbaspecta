# Uniswap V3 ASPECTA Token Swapper

A web application for swapping ASPECTA tokens on Binance Smart Chain using Uniswap V3.

## Features

- **Token Information**: Get detailed information about the ASPECTA token
- **Pool Information**: Find available Uniswap V3 pools for ASPECTA
- **Quote System**: Get swap quotes before executing transactions
- **Token Approval**: Approve tokens for swapping
- **Token Swapping**: Execute swaps with slippage protection

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Blockchain**: Web3.py for Ethereum/BSC interaction
- **Database**: SQLite with SQLAlchemy

## Installation

1. Clone the repository:
```bash
git clone https://github.com/bersamauntanmembangunnegeri/swapbnbaspecta.git
cd swapbnbaspecta
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python src/main.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Use the web interface to:
   - Check token information
   - Find available pools
   - Get swap quotes
   - Approve tokens
   - Execute swaps

## Security Warning

⚠️ **This is a demonstration tool. Never use real private keys with significant funds in a web interface like this.**

## API Endpoints

- `GET /api/token-info` - Get ASPECTA token information
- `GET /api/pool-info` - Get Uniswap V3 pool information
- `POST /api/quote` - Get swap quote
- `POST /api/approve` - Approve token for swapping
- `POST /api/swap` - Execute token swap

## Configuration

The application is configured to work with:
- **Network**: Binance Smart Chain
- **Token**: ASPECTA (0xad8c787992428cD158E451aAb109f724B6bc36de)
- **DEX**: Uniswap V3

## Deployment

For production deployment, use a WSGI server like Gunicorn:

```bash
gunicorn src.main:app
```

## License

This project is for educational and demonstration purposes.

