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
PANCAKESWAP_V3_FACTORY_ADDRESS = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKESWAP_V3_ROUTER_ADDRESS = "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4"
PANCAKESWAP_V3_QUOTER_ADDRESS = "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"

# Load ABIs
def load_abi(filename):
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    abi_path = os.path.join(parent_dir, filename)
    with open(abi_path, "r") as f:
        return json.load(f)

ERC20_ABI = load_abi("ERC20_ABI.json")
QUOTER_V2_ABI = load_abi("IQuoterV2_abi.json")
ROUTER_ABI = load_abi("UniversalRouter_abi.json")

# PancakeSwap V3 Factory ABI (simplified)
PANCAKESWAP_V3_FACTORY_ABI = [
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
    """Find PancakeSwap V3 pools for the token paired with WBNB"""
    try:
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        factory_contract = w3.eth.contract(
            address=PANCAKESWAP_V3_FACTORY_ADDRESS,
            abi=PANCAKESWAP_V3_FACTORY_ABI
        )
        
        token_address = w3.to_checksum_address(CONTRACT_ADDRESS)
        wbnb_address = w3.to_checksum_address(WBNB_ADDRESS)
        
        # PancakeSwap V3 fee tiers
        fee_tiers = [100, 500, 2500, 10000]  # 0.01%, 0.05%, 0.25%, 1%
        
        found_pools = []
        for fee in fee_tiers:
            # Check pool existence
            pool_address = factory_contract.functions.getPool(token_address, wbnb_address, fee).call()
            if pool_address != "0x0000000000000000000000000000000000000000":
                found_pools.append({
                    "address": pool_address,
                    "fee": fee,
                    "fee_percentage": f"{fee/10000}%",
                    "pair": "ASPECTA-WBNB",
                    "dex": "PancakeSwap V3"
                })
        
        return jsonify({
            "pools_found": len(found_pools),
            "pools": found_pools,
            "dex": "PancakeSwap V3",
            "note": "Using PancakeSwap V3 as it's more popular on BSC than Uniswap V3"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/quote', methods=['POST'])
def get_quote():
    """Get a quote for swapping ASPECTA to WBNB using PancakeSwap V3"""
    try:
        data = request.get_json()
        amount_in = data.get('amount_in')
        fee = data.get('fee', 10000)  # Default to 1% fee tier as it has liquidity
        
        if not amount_in:
            return jsonify({"error": "amount_in is required"}), 400
        
        if not w3.is_connected():
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        # Convert amount to wei (18 decimals for ASPECTA)
        amount_in_wei = int(amount_in * (10 ** 18))
        
        quoter_contract = w3.eth.contract(address=w3.to_checksum_address(PANCAKESWAP_V3_QUOTER_ADDRESS), abi=QUOTER_V2_ABI)
        
        # Try different fee tiers in order of preference (1% has liquidity)
        fee_tiers_to_try = [fee, 10000, 500, 100, 2500]  # Try requested fee first, then 1% (working), then others
        
        for try_fee in fee_tiers_to_try:
            try:
                # Prepare the parameters for quoteExactInputSingle
                params = {
                    "tokenIn": w3.to_checksum_address(CONTRACT_ADDRESS),
                    "tokenOut": w3.to_checksum_address(WBNB_ADDRESS),
                    "fee": try_fee,
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
                    "fee": try_fee,
                    "fee_percentage": f"{try_fee/10000}%",
                    "gas_estimate": gas_estimate,
                    "price_impact": f"1 ASPECTA = {amount_out_formatted/amount_in:.8f} WBNB",
                    "dex": "PancakeSwap V3",
                    "note": f"Using {try_fee/10000}% fee tier (has liquidity)" if try_fee != fee else None
                })
                
            except Exception as fee_error:
                # Continue to next fee tier if this one fails
                continue
        
        # If all fee tiers fail, return the original error
        return jsonify({
            "error": "No liquidity available in any fee tier for this token pair",
            "details": "ASPECTA-WBNB pools exist but may not have sufficient liquidity for this trade size",
            "suggestion": "Try a smaller amount or check if the token has liquidity on other DEXes"
        }), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/approve', methods=['POST'])
def approve_token():
    """Approve the PancakeSwap V3 Router to spend ASPECTA tokens"""
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
            w3.to_checksum_address(PANCAKESWAP_V3_ROUTER_ADDRESS),
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
            "spender": PANCAKESWAP_V3_ROUTER_ADDRESS,
            "dex": "PancakeSwap V3"
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

