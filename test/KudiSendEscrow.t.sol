// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/KudiSendEscrow.sol";

contract MockToken {
    string public name;
    uint8 public decimals;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    uint256 public feeBps; // fee-on-transfer simulation

    // reentrancy probe: when set, call `target` with `data` during transfer/transferFrom
    address public hookTarget;
    bytes public hookData;
    bool public hookSucceeded;
    bool public hookRan;

    constructor(string memory n, uint8 d) {
        name = n;
        decimals = d;
    }

    function mint(address to, uint256 a) external { balanceOf[to] += a; }
    function setFee(uint256 bps) external { feeBps = bps; }
    function setHook(address t, bytes calldata d) external { hookTarget = t; hookData = d; }
    function approve(address s, uint256 a) external returns (bool) { allowance[msg.sender][s] = a; return true; }

    function _hook() internal {
        if (hookTarget != address(0) && !hookRan) {
            hookRan = true;
            (hookSucceeded,) = hookTarget.call(hookData);
        }
    }

    function transfer(address to, uint256 a) external returns (bool) {
        _hook();
        balanceOf[msg.sender] -= a;
        balanceOf[to] += a;
        return true;
    }

    function transferFrom(address f, address to, uint256 a) external returns (bool) {
        _hook();
        allowance[f][msg.sender] -= a;
        balanceOf[f] -= a;
        uint256 fee = (a * feeBps) / 10_000;
        balanceOf[to] += a - fee;
        return true;
    }
}

contract KudiSendEscrowTest is Test {
    KudiSendEscrow esc;
    MockToken usdc;
    MockToken eurc;
    MockToken bad18;

    address owner = address(0xA11CE);
    address treasury = address(0x7EA5);
    address alice = address(0xA1);
    address bob = address(0xB0B);

    uint256 constant MIN = 10e6;
    uint256 constant MAX = 50e6;

    function setUp() public {
        usdc = new MockToken("USDC", 6);
        eurc = new MockToken("EURC", 6);
        bad18 = new MockToken("BAD", 18);
        address[] memory toks = new address[](2);
        toks[0] = address(usdc);
        toks[1] = address(eurc);
        esc = new KudiSendEscrow(owner, treasury, MIN, MAX, toks);

        usdc.mint(alice, 1000e6);
        eurc.mint(alice, 1000e6);
        usdc.mint(bob, 1000e6);
        vm.prank(alice); usdc.approve(address(esc), type(uint256).max);
        vm.prank(alice); eurc.approve(address(esc), type(uint256).max);
        vm.prank(bob); usdc.approve(address(esc), type(uint256).max);
    }

    function _dep(address who, MockToken t, uint256 amt, bytes32 ref) internal {
        vm.prank(who);
        esc.deposit(address(t), amt, ref);
    }

    // ── deposit ────────────────────────────────────────────
    function test_deposit_happy() public {
        _dep(alice, usdc, 20e6, bytes32(uint256(1)));
        (address u, address t, uint256 a,, KudiSendEscrow.State s) = esc.deposits(bytes32(uint256(1)));
        assertEq(u, alice); assertEq(t, address(usdc)); assertEq(a, 20e6);
        assertEq(uint8(s), uint8(KudiSendEscrow.State.Deposited));
        assertEq(usdc.balanceOf(address(esc)), 20e6);
    }

    function test_deposit_ref_reuse_reverts_even_after_settle() public {
        bytes32 r = bytes32(uint256(1));
        _dep(alice, usdc, 20e6, r);
        vm.expectRevert("Ref used");
        _dep(bob, usdc, 20e6, r);

        bytes32[] memory refs = new bytes32[](1); refs[0] = r;
        vm.prank(owner); esc.settle(refs);
        vm.expectRevert("Ref used");
        _dep(alice, usdc, 20e6, r);
    }

    function test_deposit_rejects_unlisted_token() public {
        bad18.mint(alice, 100e6);
        vm.prank(alice); bad18.approve(address(esc), type(uint256).max);
        vm.expectRevert("Token not allowed");
        _dep(alice, bad18, 20e6, bytes32(uint256(2)));
    }

    function test_deposit_limits_and_zero_ref() public {
        vm.expectRevert("Below minimum");
        _dep(alice, usdc, MIN - 1, bytes32(uint256(3)));
        vm.expectRevert("Above maximum");
        _dep(alice, usdc, MAX + 1, bytes32(uint256(3)));
        vm.expectRevert("Zero ref");
        _dep(alice, usdc, 20e6, bytes32(0));
        _dep(alice, usdc, MIN, bytes32(uint256(4)));
        _dep(alice, usdc, MAX, bytes32(uint256(5)));
    }

    function test_deposit_rejects_fee_on_transfer() public {
        usdc.setFee(100);
        vm.expectRevert("Inexact transfer");
        _dep(alice, usdc, 20e6, bytes32(uint256(6)));
    }

    function test_deposit_reentrancy_blocked() public {
        usdc.setHook(address(esc), abi.encodeWithSelector(esc.deposit.selector, address(usdc), 20e6, bytes32(uint256(99))));
        _dep(alice, usdc, 20e6, bytes32(uint256(7)));
        assertTrue(usdc.hookRan());
        assertFalse(usdc.hookSucceeded());
        (,,,, KudiSendEscrow.State s) = esc.deposits(bytes32(uint256(99)));
        assertEq(uint8(s), uint8(KudiSendEscrow.State.None));
    }

    // ── settle ─────────────────────────────────────────────
    function test_settle_multi_token_to_treasury() public {
        _dep(alice, usdc, 20e6, bytes32(uint256(1)));
        _dep(bob, usdc, 30e6, bytes32(uint256(2)));
        _dep(alice, eurc, 25e6, bytes32(uint256(3)));
        bytes32[] memory refs = new bytes32[](3);
        refs[0] = bytes32(uint256(1)); refs[1] = bytes32(uint256(2)); refs[2] = bytes32(uint256(3));
        vm.prank(owner); esc.settle(refs);
        assertEq(usdc.balanceOf(treasury), 50e6);
        assertEq(eurc.balanceOf(treasury), 25e6);
        assertEq(usdc.balanceOf(address(esc)), 0);
    }

    function test_settle_only_owner_and_state_checks() public {
        _dep(alice, usdc, 20e6, bytes32(uint256(1)));
        bytes32[] memory refs = new bytes32[](1); refs[0] = bytes32(uint256(1));
        vm.prank(alice);
        vm.expectRevert("Not owner");
        esc.settle(refs);

        bytes32[] memory ghost = new bytes32[](1); ghost[0] = bytes32(uint256(42));
        vm.prank(owner);
        vm.expectRevert("Not settleable");
        esc.settle(ghost);

        vm.prank(owner); esc.settle(refs);
        vm.prank(owner);
        vm.expectRevert("Not settleable"); // double settle
        esc.settle(refs);
    }

    function test_settle_duplicate_ref_in_batch_reverts() public {
        _dep(alice, usdc, 20e6, bytes32(uint256(1)));
        bytes32[] memory refs = new bytes32[](2);
        refs[0] = bytes32(uint256(1)); refs[1] = bytes32(uint256(1));
        vm.prank(owner);
        vm.expectRevert("Not settleable");
        esc.settle(refs);
    }

    function test_settle_batch_bounds() public {
        vm.prank(owner);
        vm.expectRevert("Empty batch");
        esc.settle(new bytes32[](0));
        vm.prank(owner);
        vm.expectRevert("Batch too large");
        esc.settle(new bytes32[](101));
    }

    // ── refund ─────────────────────────────────────────────
    function test_owner_refund_and_no_double_refund() public {
        bytes32 r = bytes32(uint256(1));
        _dep(alice, usdc, 20e6, r);
        vm.prank(owner); esc.refund(r);
        assertEq(usdc.balanceOf(alice), 1000e6);
        vm.prank(owner);
        vm.expectRevert("Not refundable");
        esc.refund(r);
        vm.prank(alice);
        vm.expectRevert("Not refundable");
        esc.claimRefund(r);
    }

    function test_refund_after_settle_reverts_and_settle_after_refund_reverts() public {
        bytes32 r1 = bytes32(uint256(1));
        bytes32 r2 = bytes32(uint256(2));
        _dep(alice, usdc, 20e6, r1);
        _dep(alice, usdc, 20e6, r2);
        bytes32[] memory a = new bytes32[](1); a[0] = r1;
        vm.prank(owner); esc.settle(a);
        vm.prank(owner);
        vm.expectRevert("Not refundable");
        esc.refund(r1);

        vm.prank(owner); esc.refund(r2);
        bytes32[] memory b = new bytes32[](1); b[0] = r2;
        vm.prank(owner);
        vm.expectRevert("Not settleable");
        esc.settle(b);
    }

    function test_refund_only_owner() public {
        bytes32 r = bytes32(uint256(1));
        _dep(alice, usdc, 20e6, r);
        vm.prank(alice);
        vm.expectRevert("Not owner");
        esc.refund(r);
    }

    // ── claimRefund (72h) ──────────────────────────────────
    function test_claimRefund_timing_and_auth() public {
        bytes32 r = bytes32(uint256(1));
        _dep(alice, usdc, 20e6, r);

        vm.prank(alice);
        vm.expectRevert("Too early");
        esc.claimRefund(r);

        vm.warp(block.timestamp + 72 hours - 1);
        vm.prank(alice);
        vm.expectRevert("Too early");
        esc.claimRefund(r);

        vm.warp(block.timestamp + 1);
        vm.prank(bob);
        vm.expectRevert("Not depositor");
        esc.claimRefund(r);

        vm.prank(alice); esc.claimRefund(r);
        assertEq(usdc.balanceOf(alice), 1000e6);

        vm.prank(alice);
        vm.expectRevert("Not refundable");
        esc.claimRefund(r);
    }

    function test_claimRefund_reentrancy_blocked() public {
        bytes32 r1 = bytes32(uint256(1));
        bytes32 r2 = bytes32(uint256(2));
        _dep(alice, usdc, 20e6, r1);
        _dep(alice, usdc, 20e6, r2);
        vm.warp(block.timestamp + 72 hours);
        // during the refund transfer the token tries to re-enter claimRefund for r2
        usdc.setHook(address(esc), abi.encodeWithSelector(esc.claimRefund.selector, r2));
        vm.prank(alice); esc.claimRefund(r1);
        assertTrue(usdc.hookRan());
        assertFalse(usdc.hookSucceeded());
        (,,,, KudiSendEscrow.State s) = esc.deposits(r2);
        assertEq(uint8(s), uint8(KudiSendEscrow.State.Deposited));
    }

    // ── pause ──────────────────────────────────────────────
    function test_pause_blocks_deposit_but_not_exit_paths() public {
        bytes32 r1 = bytes32(uint256(1));
        bytes32 r2 = bytes32(uint256(2));
        bytes32 r3 = bytes32(uint256(3));
        _dep(alice, usdc, 20e6, r1);
        _dep(alice, usdc, 20e6, r2);
        _dep(alice, usdc, 20e6, r3);

        vm.prank(owner); esc.setPaused(true);
        vm.expectRevert("Paused");
        _dep(alice, usdc, 20e6, bytes32(uint256(4)));

        bytes32[] memory s = new bytes32[](1); s[0] = r1;
        vm.prank(owner); esc.settle(s);
        vm.prank(owner); esc.refund(r2);
        vm.warp(block.timestamp + 72 hours);
        vm.prank(alice); esc.claimRefund(r3);
    }

    function test_setPaused_only_owner() public {
        vm.prank(alice);
        vm.expectRevert("Not owner");
        esc.setPaused(true);
    }

    // ── admin config ───────────────────────────────────────
    function test_token_allowlist_management() public {
        vm.prank(owner);
        vm.expectRevert("Token must be 6 decimals");
        esc.setTokenAllowed(address(bad18), true);

        vm.prank(owner);
        vm.expectRevert("Not a contract");
        esc.setTokenAllowed(address(0x1234), true);

        // disabling a token blocks new deposits but existing ones still exit
        _dep(alice, usdc, 20e6, bytes32(uint256(1)));
        vm.prank(owner); esc.setTokenAllowed(address(usdc), false);
        vm.expectRevert("Token not allowed");
        _dep(alice, usdc, 20e6, bytes32(uint256(2)));
        bytes32[] memory s = new bytes32[](1); s[0] = bytes32(uint256(1));
        vm.prank(owner); esc.settle(s);
        assertEq(usdc.balanceOf(treasury), 20e6);
    }

    function test_limits_and_treasury_admin() public {
        vm.prank(alice);
        vm.expectRevert("Not owner");
        esc.setLimits(1, 2);
        vm.prank(owner);
        vm.expectRevert("Bad limits");
        esc.setLimits(0, 10);
        vm.prank(owner);
        vm.expectRevert("Bad limits");
        esc.setLimits(11, 10);
        vm.prank(owner); esc.setLimits(5e6, 100e6);
        assertEq(esc.minDeposit(), 5e6);

        vm.prank(owner);
        vm.expectRevert("Zero treasury");
        esc.setTreasury(address(0));
        vm.prank(alice);
        vm.expectRevert("Not owner");
        esc.setTreasury(alice);
    }

    function test_constructor_validation() public {
        address[] memory toks = new address[](0);
        vm.expectRevert("Zero owner");
        new KudiSendEscrow(address(0), treasury, MIN, MAX, toks);
        vm.expectRevert("Zero treasury");
        new KudiSendEscrow(owner, address(0), MIN, MAX, toks);
        vm.expectRevert("Bad limits");
        new KudiSendEscrow(owner, treasury, MAX, MIN, toks);
    }

    // ── two-step ownership ─────────────────────────────────
    function test_two_step_ownership() public {
        vm.prank(alice);
        vm.expectRevert("Not owner");
        esc.transferOwnership(alice);

        vm.prank(owner); esc.transferOwnership(bob);
        assertEq(esc.owner(), owner); // not yet transferred

        vm.prank(alice);
        vm.expectRevert("Not pending owner");
        esc.acceptOwnership();

        vm.prank(bob); esc.acceptOwnership();
        assertEq(esc.owner(), bob);
        assertEq(esc.pendingOwner(), address(0));

        vm.prank(owner);
        vm.expectRevert("Not owner");
        esc.setPaused(true);
    }

    // ── invariant-style fuzz: contract balance == sum of open deposits ──
    function testFuzz_balance_matches_open_deposits(uint96 a1, uint96 a2) public {
        uint256 x = bound(a1, MIN, MAX);
        uint256 y = bound(a2, MIN, MAX);
        _dep(alice, usdc, x, bytes32(uint256(1)));
        _dep(bob, usdc, y, bytes32(uint256(2)));
        assertEq(usdc.balanceOf(address(esc)), x + y);
        vm.prank(owner); esc.refund(bytes32(uint256(1)));
        assertEq(usdc.balanceOf(address(esc)), y);
        bytes32[] memory s = new bytes32[](1); s[0] = bytes32(uint256(2));
        vm.prank(owner); esc.settle(s);
        assertEq(usdc.balanceOf(address(esc)), 0);
        assertEq(usdc.balanceOf(treasury), y);
    }
}
