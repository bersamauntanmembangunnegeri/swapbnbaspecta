from flask import Blueprint, request, jsonify
import json
import os

uniswap_bp = Blueprint('uniswap', __name__)

# Mock data for demonstration
MOCK_TOKEN_INFO = {
    "address": "0xad8c787992428cD158E451aAb109f724B6bc36de",
    "name": "ASPECTA",
    "symbol": "ASP",
    "decimals": 18,
    "total_supply": 697799412783567000000000000,
    "total_supply_formatted": "697,799,412.783567 ASP"
}

MOCK_POOL_INFO = {
    "pools_found": 2,
    "pools": [
        {
            "address": "0x7c81136D9Cf47ccCa9e50d2DC1DEF4848f3719E5",
            "fee": 500,
            "fee_percentage": "0.05%",
            "pair": "ASPECTA-WBNB"
        },
        {
            "address": "0x32D159316fd973BB60B21915F06EFf0c83885B",
            "fee": 3000,
            "fee_percentage": "0.3%",
            "pair": "ASPECTA-WBNB"
        }
    ]
}

@uniswap_bp.route('/token-info', methods=['GET'])
def get_token_info():
    """Retrieve basic information about the ASPECTA token"""
    return jsonify(MOCK_TOKEN_INFO)

@uniswap_bp.route('/pool-info', methods=['GET'])
def get_pool_info():
    """Find Uniswap V3 pools for the token paired with WBNB"""
    return jsonify(MOCK_POOL_INFO)

@uniswap_bp.route('/quote', methods=['POST'])
def get_quote():
    """Get a quote for swapping ASPECTA to WBNB"""
    try:
        data = request.get_json()
        amount_in = data.get('amount_in')
        fee = data.get('fee', 3000)
        
        if not amount_in:
            return jsonify({"error": "amount_in is required"}), 400
        
        # Mock calculation: 1 ASPECTA = 0.00001 WBNB (example rate)
        mock_rate = 0.00001
        amount_out = amount_in * mock_rate
        
        return jsonify({
            "amount_in": amount_in,
            "amount_in_wei": int(amount_in * (10 ** 18)),
            "amount_out": int(amount_out * (10 ** 18)),
            "amount_out_formatted": f"{amount_out:.6f} WBNB",
            "fee": fee,
            "fee_percentage": f"{fee/10000}%",
            "gas_estimate": 150000,
            "price_impact": f"1 ASPECTA = {mock_rate:.8f} WBNB",
            "note": "This is a mock quote for demonstration purposes"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/approve', methods=['POST'])
def approve_token():
    """Mock approve the Universal Router to spend ASPECTA tokens"""
    try:
        data = request.get_json()
        private_key = data.get('private_key')
        account_address = data.get('account_address')
        amount = data.get('amount')
        
        if not private_key or not account_address or not amount:
            return jsonify({"error": "private_key, account_address, and amount are required"}), 400
        
        # Mock transaction hash
        mock_tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        
        return jsonify({
            "success": True,
            "transaction_hash": mock_tx_hash,
            "amount_approved": amount,
            "amount_approved_wei": int(amount * (10 ** 18)),
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "note": "This is a mock approval for demonstration purposes"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@uniswap_bp.route('/swap', methods=['POST'])
def swap_token():
    """Mock perform a token swap from ASPECTA to WBNB"""
    try:
        data = request.get_json()
        private_key = data.get('private_key')
        account_address = data.get('account_address')
        amount_in = data.get('amount_in')
        amount_out_minimum = data.get('amount_out_minimum')
        fee = data.get('fee', 3000)
        
        if not private_key or not account_address or not amount_in or amount_out_minimum is None:
            return jsonify({"error": "private_key, account_address, amount_in, and amount_out_minimum are required"}), 400
        
        # Mock transaction hash
        mock_tx_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        
        return jsonify({
            "success": True,
            "transaction_hash": mock_tx_hash,
            "amount_in": amount_in,
            "amount_in_wei": int(amount_in * (10 ** 18)),
            "amount_out_minimum": amount_out_minimum,
            "amount_out_minimum_wei": int(amount_out_minimum * (10 ** 18)),
            "fee": fee,
            "fee_percentage": f"{fee/10000}%",
            "note": "This is a mock swap for demonstration purposes"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

