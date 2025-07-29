import os
from flask import Blueprint, jsonify, request
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

uniswap_bp = Blueprint("uniswap", __name__)

# Configuration
CONTRACT_ADDRESS = "0xad8c787992428cD158E451aAb109f724B6bc36de"  # ASPECTA token
BNB_CHAIN_RPC = "https://bsc-dataseed.binance.org/"
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKESWAP_V3_FACTORY_ADDRESS = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
PANCAKESWAP_V3_ROUTER_ADDRESS = "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4"
PANCAKESWAP_V3_QUOTER_ADDRESS = "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"

# Load ABIs
def load_abi(filename):
    # The ABI files are directly in the 'src' directory, which is the parent of 'routes'
    abi_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)
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
logger.info(f"Initializing Web3 with RPC: {BNB_CHAIN_RPC}")
w3 = Web3(Web3.HTTPProvider(BNB_CHAIN_RPC))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Test Web3 connection on startup
try:
    is_connected = w3.is_connected()
    chain_id = w3.eth.chain_id if is_connected else None
    logger.info(f"Web3 connection status: {is_connected}, Chain ID: {chain_id}")
except Exception as e:
    logger.error(f"Web3 connection test failed: {e}")

@uniswap_bp.route("/token-info", methods=["GET"])
def get_token_info():
    """Get ASPECTA token information"""
    logger.info("Token info request received")
    try:
        if not w3.is_connected():
            logger.error("Web3 not connected for token info")
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500

        token_contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=ERC20_ABI)

        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        total_supply = token_contract.functions.totalSupply().call()

        logger.info(f"Token info retrieved successfully: {name} ({symbol})")
        return jsonify({
            "address": CONTRACT_ADDRESS,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply": total_supply,
            "total_supply_formatted": f"{total_supply / (10 ** decimals):,.6f} {symbol}"
        })
    except Exception as e:
        logger.exception("Error getting token info")
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route("/pool-info", methods=["GET"])
def get_pool_info():
    """Find PancakeSwap V3 pools for the token paired with WBNB"""
    logger.info("Pool info request received")
    try:
        if not w3.is_connected():
            logger.error("Web3 not connected for pool info")
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
        
        logger.info(f"Found {len(found_pools)} pools")
        return jsonify({
            "pools_found": len(found_pools),
            "pools": found_pools,
            "dex": "PancakeSwap V3",
            "note": "Using PancakeSwap V3 as it\\\"s more popular on BSC than Uniswap V3"
        })
    except Exception as e:
        logger.exception("Error getting pool info")
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route("/quote", methods=["POST"])
def get_quote():
    """Get a quote for swapping ASPECTA to WBNB using PancakeSwap V3"""
    start_time = time.time()
    logger.info("Quote request received")
    
    try:
        # Log environment info
        logger.info(f"Environment check - Web3 connected: {w3.is_connected()}")
        if w3.is_connected():
            logger.info(f"Chain ID: {w3.eth.chain_id}")
            logger.info(f"Latest block: {w3.eth.block_number}")
        
        data = request.get_json()
        amount_in = data.get("amount_in")
        fee = data.get("fee", 10000)  # Default to 1% fee tier as it has liquidity
        
        logger.info(f"Request data: amount_in={amount_in}, fee={fee}, type(fee)={type(fee)}")

        if not amount_in:
            logger.error("amount_in is required")
            return jsonify({"error": "amount_in is required"}), 400
        
        if not w3.is_connected():
            logger.error("Failed to connect to BNB Smart Chain")
            return jsonify({
                "error": "Failed to connect to BNB Smart Chain",
                "debug_info": {
                    "rpc_endpoint": BNB_CHAIN_RPC,
                    "connection_test": False
                }
            }), 500
        
        # Convert amount to wei (18 decimals for ASPECTA)
        amount_in_wei = int(amount_in * (10 ** 18))
        logger.info(f"Converted amount_in to wei: {amount_in_wei}")

        # Test quoter contract initialization
        try:
            quoter_contract = w3.eth.contract(address=w3.to_checksum_address(PANCAKESWAP_V3_QUOTER_ADDRESS), abi=QUOTER_V2_ABI)
            logger.info(f"Quoter contract initialized successfully: {PANCAKESWAP_V3_QUOTER_ADDRESS}")
        except Exception as contract_error:
            logger.error(f"Failed to initialize quoter contract: {contract_error}")
            return jsonify({
                "error": "Failed to initialize quoter contract",
                "debug_info": {
                    "quoter_address": PANCAKESWAP_V3_QUOTER_ADDRESS,
                    "contract_error": str(contract_error)
                }
            }), 500

        # Try different fee tiers in order of preference (1% has liquidity)
        fee_tiers_to_try = [fee, 10000, 500, 100, 2500]  # Try requested fee first, then 1% (working), then others
        
        for try_fee in fee_tiers_to_try:
            logger.info(f"Attempting quote with fee tier: {try_fee}")
            try:
                # Prepare the parameters for quoteExactInputSingle
                params = {
                    "tokenIn": w3.to_checksum_address(CONTRACT_ADDRESS),
                    "tokenOut": w3.to_checksum_address(WBNB_ADDRESS),
                    "fee": try_fee,
                    "amountIn": amount_in_wei,
                    "sqrtPriceLimitX96": 0
                }
                logger.info(f"Quote parameters: {params}")
                
                # Test network connectivity before making the call
                try:
                    test_block = w3.eth.block_number
                    logger.info(f"Network test successful, current block: {test_block}")
                except Exception as network_error:
                    logger.error(f"Network connectivity test failed: {network_error}")
                    return jsonify({
                        "error": "Network connectivity issue",
                        "debug_info": {
                            "network_error": str(network_error),
                            "rpc_endpoint": BNB_CHAIN_RPC
                        }
                    }), 500
                
                # Call the quoteExactInputSingle function
                logger.info("Making quoteExactInputSingle call...")
                call_start = time.time()
                result = quoter_contract.functions.quoteExactInputSingle(params).call()
                call_duration = time.time() - call_start
                logger.info(f"Quote call completed in {call_duration:.2f} seconds")
                
                amount_out, sqrt_price_x96_after, initialized_ticks_crossed, gas_estimate = result
                
                # Convert amount out from wei to readable format (18 decimals for WBNB)
                amount_out_formatted = amount_out / (10 ** 18)
                logger.info(f"Quote successful with fee {try_fee}: amount_out={amount_out_formatted}")
                
                total_duration = time.time() - start_time
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
                    "note": f"Using {try_fee/10000}% fee tier (has liquidity)" if try_fee != fee else None,
                    "debug_info": {
                        "total_duration": f"{total_duration:.2f}s",
                        "call_duration": f"{call_duration:.2f}s",
                        "successful_fee_tier": try_fee
                    }
                })
                
            except Exception as fee_error:
                logger.warning(f"Quote failed for fee tier {try_fee}: {fee_error}")
                logger.warning(f"Error type: {type(fee_error).__name__}")
                # Continue to next fee tier if this one fails
                continue
        
        # If all fee tiers fail, return detailed error info
        total_duration = time.time() - start_time
        logger.error("No liquidity available in any fee tier after trying all options.")
        return jsonify({
            "error": "No liquidity available in any fee tier for this token pair",
            "details": "ASPECTA-WBNB pools exist but may not have sufficient liquidity for this trade size",
            "suggestion": "Try a smaller amount or check if the token has liquidity on other DEXes",
            "debug_info": {
                "total_duration": f"{total_duration:.2f}s",
                "fee_tiers_tried": fee_tiers_to_try,
                "rpc_endpoint": BNB_CHAIN_RPC,
                "web3_connected": w3.is_connected(),
                "chain_id": w3.eth.chain_id if w3.is_connected() else None
            }
        }), 400
        
    except Exception as e:
        total_duration = time.time() - start_time
        logger.exception("An unexpected error occurred during quote request.")
        return jsonify({
            "error": str(e),
            "debug_info": {
                "total_duration": f"{total_duration:.2f}s",
                "error_type": type(e).__name__,
                "rpc_endpoint": BNB_CHAIN_RPC
            }
        }), 500

@uniswap_bp.route("/approve", methods=["POST"])
def approve_token():
    """Approve the PancakeSwap V3 Router to spend ASPECTA tokens"""
    logger.info("Approve token request received")
    try:
        data = request.get_json()
        private_key = data.get("private_key")
        account_address = data.get("account_address")
        amount = data.get("amount")
        
        logger.info(f"Approve request: account={account_address}, amount={amount}")
        
        if not private_key or not account_address or not amount:
            logger.error("Missing required fields for approve")
            return jsonify({"error": "private_key, account_address, and amount are required"}), 400
        
        if not w3.is_connected():
            logger.error("Web3 not connected for approve")
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        # Convert amount to wei
        amount_wei = int(amount * (10 ** 18))
        logger.info(f"Amount in wei: {amount_wei}")
        
        token_contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=ERC20_ABI)
        account_address = w3.to_checksum_address(account_address)
        nonce = w3.eth.get_transaction_count(account_address)
        
        logger.info(f"Account nonce: {nonce}")
        
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
        
        logger.info(f"Transaction built: {txn}")
        
        # Sign the transaction
        logger.info("Signing transaction...")
        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        logger.info(f"Transaction signed, type: {type(signed_txn)}")
        
        # Fix for the rawTransaction attribute error
        # In newer versions of web3.py, it might be \'raw_transaction\' instead of \'rawTransaction\'
        raw_transaction = None
        if hasattr(signed_txn, 'rawTransaction'):
            raw_transaction = signed_txn.rawTransaction
            logger.info("Using rawTransaction attribute")
        elif hasattr(signed_txn, 'raw_transaction'):
            raw_transaction = signed_txn.raw_transaction
            logger.info("Using raw_transaction attribute")
        else:
            logger.error(f"Signed transaction object attributes: {dir(signed_txn)}")
            return jsonify({
                "error": "Unable to access raw transaction data",
                "debug_info": {
                    "signed_txn_type": str(type(signed_txn)),
                    "available_attributes": [attr for attr in dir(signed_txn) if not attr.startswith('_')]
                }
            }), 500
        
        # Send the transaction
        logger.info("Sending transaction...")
        tx_hash = w3.eth.send_raw_transaction(raw_transaction)
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "amount_approved": amount,
            "amount_approved_wei": amount_wei,
            "spender": PANCAKESWAP_V3_ROUTER_ADDRESS,
            "dex": "PancakeSwap V3"
        })
    except Exception as e:
        logger.exception("Error in approve token")
        return jsonify({
            "error": str(e),
            "debug_info": {
                "error_type": type(e).__name__
            }
        }), 500

@uniswap_bp.route("/swap", methods=["POST"])
def swap_token():
    """Perform a token swap from ASPECTA to WBNB using PancakeSwap V3"""
    logger.info("Swap token request received")
    try:
        data = request.get_json()
        private_key = data.get("private_key")
        account_address = data.get("account_address")
        amount_in = data.get("amount_in")
        amount_out_min = data.get("amount_out_min")
        fee = data.get("fee")
        
        logger.info(f"Swap request: account={account_address}, amount_in={amount_in}, amount_out_min={amount_out_min}, fee={fee}")
        
        if not all([private_key, account_address, amount_in, amount_out_min, fee]):
            logger.error("Missing required fields for swap")
            return jsonify({"error": "private_key, account_address, amount_in, amount_out_min, and fee are required"}), 400
        
        if not w3.is_connected():
            logger.error("Web3 not connected for swap")
            return jsonify({"error": "Failed to connect to BNB Smart Chain"}), 500
        
        # Convert amounts to wei
        amount_in_wei = int(amount_in * (10 ** 18))
        amount_out_min_wei = int(amount_out_min * (10 ** 18))
        
        account_address = w3.to_checksum_address(account_address)
        
        # Get the current nonce for the account
        nonce = w3.eth.get_transaction_count(account_address)
        logger.info(f"Account nonce: {nonce}")
        
        # Get the router contract
        router_contract = w3.eth.contract(address=w3.to_checksum_address(PANCAKESWAP_V3_ROUTER_ADDRESS), abi=ROUTER_ABI)
        
        # Example parameters for exactInputSingle (PancakeSwap V3 Router)
        swap_params = (
            w3.to_checksum_address(CONTRACT_ADDRESS),  # tokenIn
            w3.to_checksum_address(WBNB_ADDRESS),      # tokenOut
            fee,                                       # fee
            account_address,                           # recipient
            amount_in_wei,                             # amountIn
            amount_out_min_wei,                        # amountOutMinimum
            0                                          # sqrtPriceLimitX96 (0 for no limit)
        )
        
        logger.info(f"Swap parameters: {swap_params}")
        
        # Build the transaction
        txn = router_contract.functions.exactInputSingle(swap_params).build_transaction({
            "chainId": w3.eth.chain_id,
            "gas": 500000,  # Increased gas limit for swaps
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
        })
        
        logger.info(f"Swap transaction built: {txn}")
        
        # Sign the transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        
        # Fix for the rawTransaction attribute error (same as approve)
        raw_transaction = None
        if hasattr(signed_txn, 'rawTransaction'):
            raw_transaction = signed_txn.rawTransaction
        elif hasattr(signed_txn, 'raw_transaction'):
            raw_transaction = signed_txn.raw_transaction
        else:
            logger.error(f"Signed transaction object attributes: {dir(signed_txn)}")
            return jsonify({
                "error": "Unable to access raw transaction data",
                "debug_info": {
                    "signed_txn_type": str(type(signed_txn)),
                    "available_attributes": [attr for attr in dir(signed_txn) if not attr.startswith('_')]
                }
            }), 500
        
        # Send the transaction
        logger.info("Sending transaction...")
        tx_hash = w3.eth.send_raw_transaction(raw_transaction)
        logger.info(f"Swap transaction sent: {tx_hash.hex()}")
        
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "amount_in": amount_in,
            "amount_out_min": amount_out_min,
            "fee": fee,
            "dex": "PancakeSwap V3"
        })
    except Exception as e:
        logger.exception("Error in swap token")
        return jsonify({
            "error": str(e),
            "debug_info": {
                "error_type": type(e).__name__
            }
        }), 500

