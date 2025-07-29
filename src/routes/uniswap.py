from flask import Blueprint, request, jsonify
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import json
import os
import time

uniswap_bp = Blueprint('uniswap', __name__)

# Configuration
CONTRACT_ADDRESS = "0xad8c787992428cD158E451aAb109f724B6bc36de"  # ASPECTA token
BNB_CHAIN_RPC = "https://bsc-dataseed.binance.org/"
UNISWAP_V3_FACTORY_ADDRESS = "0xdB1d10011AD0Ff90774D0C6Bb92e5C5c8b4461F7"
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
UNIVERSAL_ROUTER_ADDRESS = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
QUOTER_V2_ADDRESS = "0x78D78E420Da98ad378D7799bE8f4AF69033EB077"

# Load ABIs
def load_abi(filename):
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    abi_path = os.path.join(parent_dir, filename)
    with open(abi_path, "r") as f:
        return json.load(f)

ERC20_ABI = load_abi("ERC20_ABI.json")
QUOTER_V2_ABI = load_abi("IQuoterV2_abi.json")
UNIVERSAL_ROUTER_ABI = load_abi("UniversalRouter_abi.json")

# Uniswap V3 Factory ABI (simplified)
UNISWAP_V3_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"}
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(BNB_CHAIN_RPC))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

@uniswap_bp.route('/token-info', methods=['GET'])
def get_token_info():
    """Retrieve basic information about the ASPECTA token"""
    try:
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        token_contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=ERC20_ABI)
        
        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        total_supply = token_contract.functions.totalSupply().call()
        
        return jsonify({
            "address": CONTRACT_ADDRESS,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply": total_supply,
            "total_supply_formatted": f"{total_supply / (10 ** decimals):,} {symbol}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/pool-info', methods=['GET'])
def get_pool_info():
    """Find Uniswap V3 pools for the token paired with WBNB"""
    try:
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        factory_contract = w3.eth.contract(
            address=UNISWAP_V3_FACTORY_ADDRESS,
            abi=UNISWAP_V3_FACTORY_ABI
        )
        
        token_address = w3.to_checksum_address(CONTRACT_ADDRESS)
        wbnb_address = w3.to_checksum_address(WBNB_ADDRESS)
        
        # Common Uniswap V3 fee tiers
        fee_tiers = [100, 500, 3000, 10000]  # 0.01%, 0.05%, 0.3%, 1%
        
        found_pools = []
        for fee in fee_tiers:
            # Check both token orderings
            pool_address_1 = factory_contract.functions.getPool(token_address, wbnb_address, fee).call()
            if pool_address_1 != "0x0000000000000000000000000000000000000000":
                found_pools.append({
                    "address": pool_address_1,
                    "fee": fee,
                    "fee_percentage": f"{fee/10000}%",
                    "pair": "ASPECTA-WBNB"
                })
            
            pool_address_2 = factory_contract.functions.getPool(wbnb_address, token_address, fee).call()
            if pool_address_2 != "0x0000000000000000000000000000000000000000" and pool_address_2 != pool_address_1:
                found_pools.append({
                    "address": pool_address_2,
                    "fee": fee,
                    "fee_percentage": f"{fee/10000}%",
                    "pair": "WBNB-ASPECTA"
                })
        
        return jsonify({
            "pools_found": len(found_pools),
            "pools": found_pools
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/quote', methods=['POST'])
def get_quote():
    """Get a quote for swapping ASPECTA to WBNB"""
    try:
        data = request.get_json()
        amount_in = data.get('amount_in')
        fee = data.get('fee', 3000)
        
        if not amount_in:
            return jsonify({"error": "amount_in is required"}), 400
        
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        # Convert amount to wei (18 decimals for ASPECTA)
        amount_in_wei = int(amount_in * (10 ** 18))
        
        quoter_contract = w3.eth.contract(address=w3.to_checksum_address(QUOTER_V2_ADDRESS), abi=QUOTER_V2_ABI)
        
        # Prepare the parameters for quoteExactInputSingle
        params = {
            "tokenIn": w3.to_checksum_address(CONTRACT_ADDRESS),
            "tokenOut": w3.to_checksum_address(WBNB_ADDRESS),
            "fee": fee,
            "amountIn": amount_in_wei,
            "sqrtPriceLimitX96": 0
        }
        
        # Call the quoteExactInputSingle function
        result = quoter_contract.functions.quoteExactInputSingle(params).call()
        amount_out, sqrt_price_x96_after, initialized_ticks_crossed, gas_estimate = result
        
        # Convert amount out from wei to readable format (18 decimals for WBNB)
        amount_out_formatted = amount_out / (10 ** 18)
        
        return jsonify({
            "amount_in": amount_in,
            "amount_in_wei": amount_in_wei,
            "amount_out": amount_out,
            "amount_out_formatted": f"{amount_out_formatted:.6f} WBNB",
            "fee": fee,
            "fee_percentage": f"{fee/10000}%",
            "gas_estimate": gas_estimate,
            "price_impact": f"1 ASPECTA = {amount_out_formatted/amount_in:.8f} WBNB"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/approve', methods=['POST'])
def approve_token():
    """Approve the Universal Router to spend ASPECTA tokens"""
    try:
        data = request.get_json()
        private_key = data.get('private_key')
        account_address = data.get('account_address')
        amount = data.get('amount')
        
        if not private_key or not account_address or not amount:
            return jsonify({"error": "private_key, account_address, and amount are required"}), 400
        
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        # Convert amount to wei
        amount_wei = int(amount * (10 ** 18))
        
        token_contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=ERC20_ABI)
        account_address = w3.to_checksum_address(account_address)
        nonce = w3.eth.get_transaction_count(account_address)
        
        # Build the transaction
        txn = token_contract.functions.approve(
            w3.to_checksum_address(UNIVERSAL_ROUTER_ADDRESS),
            amount_wei
        ).build_transaction({
            "chainId": w3.eth.chain_id,
            "gas": 200000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
        })
        
        # Sign the transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        
        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "amount_approved": amount,
            "amount_approved_wei": amount_wei,
            "spender": UNIVERSAL_ROUTER_ADDRESS
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/swap', methods=['POST'])
def swap_token():
    """Perform a token swap from ASPECTA to WBNB"""
    try:
        data = request.get_json()
        private_key = data.get('private_key')
        account_address = data.get('account_address')
        amount_in = data.get('amount_in')
        amount_out_minimum = data.get('amount_out_minimum')
        fee = data.get('fee', 3000)
        
        if not private_key or not account_address or not amount_in or amount_out_minimum is None:
            return jsonify({"error": "private_key, account_address, amount_in, and amount_out_minimum are required"}), 400
        
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        # Convert amounts to wei
        amount_in_wei = int(amount_in * (10 ** 18))
        amount_out_minimum_wei = int(amount_out_minimum * (10 ** 18))
        
        universal_router_contract = w3.eth.contract(address=w3.to_checksum_address(UNIVERSAL_ROUTER_ADDRESS), abi=UNIVERSAL_ROUTER_ABI)
        account_address = w3.to_checksum_address(account_address)
        nonce = w3.eth.get_transaction_count(account_address)
        
        # Command for V3_SWAP_EXACT_IN (0x00)
        commands = b'\x00'
        
        # Input for V3_SWAP_EXACT_IN
        inputs_encoded = w3.codec.encode(
            [
                "address", "address", "uint256", "uint256", "uint24", "address", "uint160"
            ],
            [
                w3.to_checksum_address(CONTRACT_ADDRESS),
                w3.to_checksum_address(WBNB_ADDRESS),
                amount_in_wei,
                amount_out_minimum_wei,
                fee,
                account_address,
                0  # sqrtPriceLimitX96
            ]
        )
        
        inputs = [inputs_encoded]
        
        # Set a deadline for the transaction (5 minutes from now)
        deadline = int(time.time()) + 300
        
        # Build the transaction
        txn = universal_router_contract.functions.execute(
            commands,
            inputs,
            deadline
        ).build_transaction({
            "chainId": w3.eth.chain_id,
            "from": account_address,
            "gas": 1000000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "value": 0  # No BNB sent since we're swapping from ASPECTA
        })
        
        # Sign the transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        
        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "amount_in": amount_in,
            "amount_in_wei": amount_in_wei,
            "amount_out_minimum": amount_out_minimum,
            "amount_out_minimum_wei": amount_out_minimum_wei,
            "fee": fee,
            "fee_percentage": f"{fee/10000}%"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

