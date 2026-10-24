// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Script.sol";
import "../src/KudiSendEscrow.sol";

/// Deploys KudiSendEscrow. The deployer only pays gas; ESCROW_OWNER controls it.
contract DeployEscrow is Script {
    // Arc Testnet token addresses (override via env for other networks)
    address constant USDC_TESTNET = 0x3600000000000000000000000000000000000000;
    address constant EURC_TESTNET = 0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a;

    function run() external returns (KudiSendEscrow esc) {
        address owner = vm.envAddress("ESCROW_OWNER");
        address treasury = vm.envAddress("ESCROW_TREASURY");
        uint256 minDep = vm.envOr("ESCROW_MIN", uint256(10e6));
        uint256 maxDep = vm.envOr("ESCROW_MAX", uint256(50e6));

        address[] memory tokens = new address[](2);
        tokens[0] = vm.envOr("ESCROW_USDC", USDC_TESTNET);
        tokens[1] = vm.envOr("ESCROW_EURC", EURC_TESTNET);

        vm.startBroadcast();
        esc = new KudiSendEscrow(owner, treasury, minDep, maxDep, tokens);
        vm.stopBroadcast();

        console.log("KudiSendEscrow:", address(esc));
    }
}
