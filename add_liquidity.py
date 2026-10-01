import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

try:
    from web3 import Web3
except ImportError:
    print("❌ Run: pip install web3 --break-system-packages"); sys.exit(1)

ARC_RPC   = "https://rpc.testnet.arc.network"
CHAIN_ID  = 5042002
OWNER_PK  = os.getenv("OWNER_PRIVATE_KEY","")
USDC_ADDR = "0x3600000000000000000000000000000000000000"
EURC_ADDR = "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"
USDC_SEED = 100.0
EURC_SEED = 100.0

CONTRACT_ADDR = os.getenv("KUDI_CONTRACT_ADDRESS","")
if not CONTRACT_ADDR and Path("deployment.json").exists():
    CONTRACT_ADDR = json.load(open("deployment.json")).get("address","")
if not CONTRACT_ADDR:
    print("❌ No contract address. Run deploy.py first."); sys.exit(1)

print(f"\n💧 Adding liquidity to KudiSwap")
print(f"   Contract: {CONTRACT_ADDR}")
w3 = Web3(Web3.HTTPProvider(ARC_RPC))
account = w3.eth.account.from_key(OWNER_PK)
print(f"   Wallet  : {account.address}")

ERC20_ABI = [
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]
KUDI_ABI = [
    {"inputs":[{"name":"token","type":"address"},{"name":"amount","type":"uint256"}],"name":"addLiquidity","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"getPoolBalances","outputs":[{"name":"usdcBalance","type":"uint256"},{"name":"eurcBalance","type":"uint256"}],"stateMutability":"view","type":"function"}
]

usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDR), abi=ERC20_ABI)
eurc = w3.eth.contract(address=Web3.to_checksum_address(EURC_ADDR), abi=ERC20_ABI)
kudi = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDR), abi=KUDI_ABI)

usdc_bal = usdc.functions.balanceOf(account.address).call()
eurc_bal = eurc.functions.balanceOf(account.address).call()
print(f"\n   Your balances: USDC={usdc_bal/1e6:.4f} | EURC={eurc_bal/1e6:.4f}")

usdc_amount = min(int(USDC_SEED*1e6), usdc_bal)
eurc_amount = min(int(EURC_SEED*1e6), eurc_bal)

if usdc_amount == 0 and eurc_amount == 0:
    print("⚠️  No tokens to add. Get from: https://faucet.circle.com"); sys.exit(1)

def send_tx(txn, label):
    txn["nonce"]=w3.eth.get_transaction_count(account.address); txn["chainId"]=CHAIN_ID; txn["gasPrice"]=w3.eth.gas_price; txn.pop("maxFeePerGas",None); txn.pop("maxPriorityFeePerGas",None)
    txn["gas"] = int(w3.eth.estimate_gas(txn)*1.2)
    signed  = w3.eth.account.sign_transaction(txn, OWNER_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"   📤 {label}: {tx_hash.hex()[:22]}...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"]==0:
        print(f"   ❌ {label} REVERTED"); return False
    print(f"   ✅ {label} confirmed"); return True

if usdc_amount > 0:
    print(f"\n1️⃣  Adding {usdc_amount/1e6:.2f} USDC...")
    if not send_tx(usdc.functions.approve(Web3.to_checksum_address(CONTRACT_ADDR), usdc_amount).build_transaction({"from":account.address}), "Approve USDC"): sys.exit(1)
    if not send_tx(kudi.functions.addLiquidity(Web3.to_checksum_address(USDC_ADDR), usdc_amount).build_transaction({"from":account.address}), "Add USDC"): sys.exit(1)

if eurc_amount > 0:
    print(f"\n2️⃣  Adding {eurc_amount/1e6:.2f} EURC...")
    if not send_tx(eurc.functions.approve(Web3.to_checksum_address(CONTRACT_ADDR), eurc_amount).build_transaction({"from":account.address}), "Approve EURC"): sys.exit(1)
    if not send_tx(kudi.functions.addLiquidity(Web3.to_checksum_address(EURC_ADDR), eurc_amount).build_transaction({"from":account.address}), "Add EURC"): sys.exit(1)

usdc_pool, eurc_pool = kudi.functions.getPoolBalances().call()
print(f"\n{'='*45}")
print(f"✅  Pool seeded!")
print(f"   USDC in pool : {usdc_pool/1e6:.4f}")
print(f"   EURC in pool : {eurc_pool/1e6:.4f}")
print(f"   Explorer     : https://testnet.arcscan.app/address/{CONTRACT_ADDR}")
print(f"{'='*45}")
print("\n🎉 KudiSwap is ready for swaps!")
