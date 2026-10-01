// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function transfer(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
    function approve(address, uint256) external returns (bool);
}

interface ITeller {
    function deposit(uint256 _assets, address _receiver) external returns (uint256);
    function redeem(uint256 _shares, address _receiver, address _account) external returns (uint256);
}

/**
 * @title  KudiYield
 * @notice Wrapper that holds USYC allowlist approval on behalf of all KudiArc users.
 *         Users deposit USDC → contract mints USYC → tracks each user's share.
 *         Users withdraw → contract redeems USYC → returns USDC to user.
 *
 * Deploy this contract, then request Circle to allowlist THIS contract address.
 * Individual users never need to be allowlisted.
 */
contract KudiYield {

    // ── Constants ────────────────────────────────────────────────────────────
    address public constant USDC   = 0x3600000000000000000000000000000000000000;
    address public constant USYC   = 0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C;
    address public constant TELLER = 0x9fdF14c5B14173D74C08Af27AebFf39240dC105A;

    // ── State ────────────────────────────────────────────────────────────────
    address public owner;
    bool    public paused;

    // User's USYC share balance tracked internally
    mapping(address => uint256) public usycShares;
    uint256 public totalShares;

    // ── Events ───────────────────────────────────────────────────────────────
    event Deposited(address indexed user, uint256 usdcIn, uint256 usycOut);
    event Withdrawn(address indexed user, uint256 usycIn, uint256 usdcOut);

    // ── Modifiers ────────────────────────────────────────────────────────────
    modifier onlyOwner()  { require(msg.sender == owner, "Not owner"); _; }
    modifier notPaused()  { require(!paused, "Paused"); _; }

    // ── Constructor ──────────────────────────────────────────────────────────
    constructor() {
        owner = msg.sender;
        // Pre-approve Teller to spend this contract's USDC (max allowance)
        IERC20(USDC).approve(TELLER, type(uint256).max);
        IERC20(USYC).approve(TELLER, type(uint256).max);
        // Pre-approve Teller to spend this contract's USYC for redemptions
        IERC20(USYC).approve(TELLER, type(uint256).max);
    }

    // ── User functions ───────────────────────────────────────────────────────

    /**
     * @notice Deposit USDC. Contract mints USYC via Teller and credits user's share.
     * @param  usdcAmount  Amount of USDC to deposit (6 decimals)
     */
    function deposit(uint256 usdcAmount) external notPaused returns (uint256 usycReceived) {
        require(usdcAmount >= 1e6, "Minimum 1 USDC");

        // Pull USDC from user
        IERC20(USDC).transferFrom(msg.sender, address(this), usdcAmount);

        // Deposit into Teller — contract (allowlisted) receives USYC
        usycReceived = ITeller(TELLER).deposit(usdcAmount, address(this));
        require(usycReceived > 0, "No USYC minted");

        // Track user's share
        usycShares[msg.sender] += usycReceived;
        totalShares             += usycReceived;

        emit Deposited(msg.sender, usdcAmount, usycReceived);
    }

    /**
     * @notice Withdraw by burning USYC shares. Returns USDC to user.
     * @param  usycAmount  Amount of USYC shares to redeem (6 decimals)
     */
    function withdraw(uint256 usycAmount) external notPaused returns (uint256 usdcReceived) {
        require(usycShares[msg.sender] >= usycAmount, "Insufficient shares");

        // Burn shares before external call (CEI — reentrancy protection)
        usycShares[msg.sender] -= usycAmount;
        totalShares             -= usycAmount;

        // Redeem USYC → USDC to THIS contract first (only allowlisted address can be receiver)
        usdcReceived = ITeller(TELLER).redeem(usycAmount, address(this), address(this));
        require(usdcReceived > 0, "No USDC returned");

        // Transfer USDC from contract to user
        IERC20(USDC).transfer(msg.sender, usdcReceived);

        emit Withdrawn(msg.sender, usycAmount, usdcReceived);
    }

    // ── View functions ───────────────────────────────────────────────────────

    /** @notice User's USYC share balance */
    function balanceOf(address user) external view returns (uint256) {
        return usycShares[user];
    }

    /** @notice Total USYC held by this contract */
    function totalUsyc() external view returns (uint256) {
        return IERC20(USYC).balanceOf(address(this));
    }

    // ── Admin ────────────────────────────────────────────────────────────────

    function setPaused(bool _p) external onlyOwner { paused = _p; }

    /** @notice Re-approve Teller for both USDC and USYC if allowance runs out */
    function reapprove() external onlyOwner {
        IERC20(USDC).approve(TELLER, type(uint256).max);
        IERC20(USYC).approve(TELLER, type(uint256).max);
        IERC20(USYC).approve(TELLER, type(uint256).max);
    }

    /** @notice Emergency: recover any stuck tokens (not USYC — that belongs to users) */
    function recoverToken(address token, uint256 amount) external onlyOwner {
        require(token != USYC, "Cannot recover USYC - belongs to users");
        IERC20(token).transfer(owner, amount);
    }
}
