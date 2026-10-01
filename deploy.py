import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

try:
    from web3 import Web3
    from solcx import compile_source, install_solc, get_installed_solc_versions
except ImportError:
    print("❌ Run: pip install web3 py-solc-x python-dotenv --break-system-packages")
    sys.exit(1)

ARC_RPC  = "https://rpc.testnet.arc.network"
CHAIN_ID = 5042002
OWNER_PK = os.getenv("OWNER_PRIVATE_KEY", "")
INIT_USDC_TO_EURC = 863827  # 0.8638 current live rate
INIT_EURC_TO_USDC = 1157639  # 1.1576 current live rate

if not OWNER_PK:
    print("❌ OWNER_PRIVATE_KEY not set in .env"); sys.exit(1)
if not Path("KudiSwap.sol").exists():
    print("❌ KudiSwap.sol not found"); sys.exit(1)

print("\n🔗 Connecting to Arc Testnet...")
w3 = Web3(Web3.HTTPProvider(ARC_RPC))
if not w3.is_connected():
    print("❌ Could not connect to Arc RPC"); sys.exit(1)

print(f"✅ Connected | Block: {w3.eth.block_number}")
account = w3.eth.account.from_key(OWNER_PK)
print(f"📬 Deployer: {account.address}")

balance_wei  = w3.eth.get_balance(account.address)
balance_usdc = balance_wei / 1e18
print(f"💰 Balance: {balance_usdc:.4f} USDC")

if balance_usdc < 0.01:
    print("\n⚠️  Low balance! Get testnet USDC from:")
    print("   https://faucet.circle.com → Select Arc Testnet → Request USDC")
    sys.exit(1)

print("\n🔧 Setting up Solidity compiler...")
SOLC_VERSION = "0.8.24"
installed = get_installed_solc_versions()
if not any(str(v) == SOLC_VERSION for v in installed):
    print(f"   Installing solc {SOLC_VERSION}...")
    install_solc(SOLC_VERSION)
print(f"   ✅ solc {SOLC_VERSION} ready")

print("\n📦 Compiling KudiSwap.sol...")
with open("KudiSwapV2.sol") as f:
    source_code = f.read()

try:
    compiled = compile_source(source_code, output_values=["abi","bin"], solc_version=SOLC_VERSION, optimize=True, optimize_runs=200)
except Exception as e:
    print(f"❌ Compilation failed: {e}"); sys.exit(1)

contract_data = compiled["<stdin>:KudiSwapV2"]
abi      = contract_data["abi"]
bytecode = contract_data["bin"]
print(f"   ✅ Compiled | Bytecode: {len(bytecode)//2} bytes")

print(f"\n🚀 Deploying to Arc Testnet (Chain {CHAIN_ID})...")
Contract  = w3.eth.contract(abi=abi, bytecode=bytecode)
nonce     = w3.eth.get_transaction_count(account.address)
gas_price = w3.eth.gas_price

deploy_txn = Contract.constructor(
        "0x3600000000000000000000000000000000000000",
        "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a",
        INIT_USDC_TO_EURC,
        INIT_EURC_TO_USDC
    ).build_transaction({
    "chainId": CHAIN_ID, "from": account.address,
    "nonce": nonce, "gasPrice": gas_price,
})

try:
    deploy_txn["gas"] = int(w3.eth.estimate_gas(deploy_txn) * 1.2)
    gas_cost = (deploy_txn["gas"] * gas_price) / 1e18
    print(f"   Gas: {deploy_txn['gas']:,} | Cost: ~{gas_cost:.6f} USDC")
except Exception as e:
    print(f"❌ Gas estimation failed: {e}"); sys.exit(1)

signed  = w3.eth.account.sign_transaction(deploy_txn, OWNER_PK)
print("\n   Sending transaction...")
try:
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"   📤 TX: {tx_hash.hex()}")
    print(f"   🔍 https://testnet.arcscan.app/tx/{tx_hash.hex()}")
except Exception as e:
    print(f"❌ TX failed: {e}"); sys.exit(1)

print("\n⏳ Waiting for confirmation...")
try:
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
except Exception as e:
    print(f"❌ Timeout: {e}"); sys.exit(1)

if receipt["status"] == 0:
    print("❌ Transaction REVERTED"); sys.exit(1)

contract_address = receipt["contractAddress"]
gas_cost_actual  = (receipt["gasUsed"] * gas_price) / 1e18

print(f"\n{'='*50}")
print(f"✅  DEPLOYED SUCCESSFULLY!")
print(f"   Address : {contract_address}")
print(f"   TX      : {tx_hash.hex()}")
print(f"   Block   : {receipt['blockNumber']}")
print(f"   Gas Cost: {gas_cost_actual:.6f} USDC")
print(f"   Explorer: https://testnet.arcscan.app/address/{contract_address}")
print(f"{'='*50}")

with open("deployment.json","w") as f:
    json.dump({"contract":"KudiSwapV2","address":contract_address,"tx_hash":tx_hash.hex(),"block":receipt["blockNumber"],"chain_id":CHAIN_ID,"deployer":account.address,"abi":abi}, f, indent=2)
print("📄 Saved to deployment.json")

env_path = Path(".env")
content  = env_path.read_text()
if "KUDI_CONTRACT_ADDRESS=" in content:
    lines = [f"KUDI_CONTRACT_ADDRESS={contract_address}" if l.startswith("KUDI_CONTRACT_ADDRESS=") else l for l in content.splitlines()]
    env_path.write_text("\n".join(lines)+"\n")
else:
    with env_path.open("a") as f:
        f.write(f"\nKUDI_CONTRACT_ADDRESS={contract_address}\n")
print("✅ .env updated")

print(f"""
📋 NEXT STEPS:
  1. Get testnet USDC+EURC: https://faucet.circle.com
  2. Run: python3 add_liquidity.py
  3. Then start the Flask backend
""")
