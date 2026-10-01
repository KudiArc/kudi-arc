// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title KudiSwap V2
 * @author Kudi Arc — Built in Nigeria
 * @notice USDC <-> EURC FX swap on Arc Network
 * @dev Custodial FX engine with reentrancy guard, timelocks,
 *      rate bounds, SafeERC20, and two-step ownership
 */

// ── SafeERC20 (inline, no imports needed) ─────────────────────
interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function decimals() external view returns (uint8);
}

library SafeERC20 {
    function safeTransfer(IERC20 token, address to, uint256 amount) internal {
        (bool success, bytes memory data) = address(token).call(
            abi.encodeWithSelector(token.transfer.selector, to, amount)
        );
        require(success && (data.length == 0 || abi.decode(data, (bool))),
            "SafeERC20: transfer failed");
    }

    function safeTransferFrom(IERC20 token, address from, address to, uint256 amount) internal {
        (bool success, bytes memory data) = address(token).call(
            abi.encodeWithSelector(token.transferFrom.selector, from, to, amount)
        );
        require(success && (data.length == 0 || abi.decode(data, (bool))),
            "SafeERC20: transferFrom failed");
    }
}

// ── Main Contract ──────────────────────────────────────────────
contract KudiSwapV2 {
    using SafeERC20 for IERC20;

    // ── State ──────────────────────────────────────────────
    address public owner;
    address public pendingOwner;
    bool    public paused;
    bool    private _locked;

    IERC20 public immutable USDC;
    IERC20 public immutable EURC;

    uint256 public usdcToEurcRate;
    uint256 public eurcToUsdcRate;
    uint256 public feeBps = 30;

    // ── Constants ──────────────────────────────────────────
    uint256 public constant MAX_FEE             = 200;       // 2%
    uint256 public constant RATE_DELAY          = 5 minutes;
    uint256 public constant WITHDRAW_DELAY      = 24 hours;
    uint256 public constant MAX_RATE_CHANGE_PCT = 20;        // 20% max rate deviation per update
    uint256 public constant MIN_LIQUIDITY       = 1_000_000; // 1 USDC/EURC minimum always in pool
    uint256 public constant MAX_WITHDRAW_PCT    = 50;        // max 50% of pool per withdrawal
    uint256 public constant MIN_RATE            = 500_000;   // 0.5 absolute minimum rate
    uint256 public constant MAX_RATE            = 2_000_000; // 2.0 absolute maximum rate

    // ── Pending Actions ────────────────────────────────────
    struct PendingRate {
        uint256 usdcToEurc;
        uint256 eurcToUsdc;
        uint256 effectiveAt;
    }

    struct PendingWithdraw {
        address token;
        uint256 amount;
        uint256 effectiveAt;
    }

    PendingRate    public pendingRate;
    PendingWithdraw public pendingWithdraw;

    // ── Stats ──────────────────────────────────────────────
    uint256 public totalUsdcSwapped;
    uint256 public totalEurcSwapped;
    uint256 public totalSwaps;
    uint256 public totalFeesCollected;
    uint256 public accruedFees;      // fees separated from liquidity

    // ── Events ─────────────────────────────────────────────
    /// @notice Emitted on every successful swap
    event Swapped(
        address indexed user,
        address indexed fromToken,
        address indexed toToken,
        uint256 amountIn,
        uint256 amountOut,
        uint256 fee
    );

    /// @notice Emitted when a rate update is queued
    event RateUpdateQueued(
        uint256 usdcToEurc,
        uint256 eurcToUsdc,
        uint256 effectiveAt
    );

    /// @notice Emitted when queued rate is applied
    event RateApplied(uint256 usdcToEurc, uint256 eurcToUsdc);

    /// @notice Emitted when a withdrawal is queued
    event WithdrawQueued(address indexed token, uint256 amount, uint256 effectiveAt);

    /// @notice Emitted when queued withdrawal executes
    event WithdrawExecuted(address indexed token, uint256 amount, address to);

    /// @notice Emitted when liquidity is added
    event LiquidityAdded(address indexed token, uint256 amount);

    /// @notice Emitted when fee is updated
    event FeeUpdated(uint256 oldFee, uint256 newFee);
    /// @notice Emitted when accrued fees are withdrawn
    event FeesWithdrawn(address indexed token, uint256 amount);

    /// @notice Emitted when ownership transfer is initiated
    event OwnershipTransferQueued(address indexed newOwner);

    /// @notice Emitted when new owner accepts
    event OwnershipTransferred(address indexed oldOwner, address indexed newOwner);

    /// @notice Emitted when contract is paused or unpaused
    event PauseToggled(bool paused);

    // ── Modifiers ──────────────────────────────────────────
    /// @dev Restricts to contract owner only
    modifier onlyOwner() {
        require(msg.sender == owner, "KudiSwap: not owner");
        _;
    }

    /// @dev Reverts when contract is paused
    modifier notPaused() {
        require(!paused, "KudiSwap: paused");
        _;
    }

    /// @dev Prevents reentrancy attacks
    modifier nonReentrant() {
        require(!_locked, "KudiSwap: reentrant call");
        _locked = true;
        _;
        _locked = false;
    }

    // ── Constructor ────────────────────────────────────────
    /**
     * @notice Deploy KudiSwap V2
     * @param _usdc USDC token address (Arc testnet: 0x3600...)
     * @param _eurc EURC token address (Arc testnet: 0x89B5...)
     * @param _usdcToEurcRate Initial rate * 1e6 (e.g. 863827 = 0.8638 EURC per USDC)
     * @param _eurcToUsdcRate Initial rate * 1e6 (e.g. 1157639 = 1.1576 USDC per EURC)
     */
    constructor(
        address _usdc,
        address _eurc,
        uint256 _usdcToEurcRate,
        uint256 _eurcToUsdcRate
    ) {
        require(_usdc != address(0) && _eurc != address(0), "KudiSwap: zero address");
        require(_usdc != _eurc, "KudiSwap: same token");
        require(_usdcToEurcRate > 0 && _eurcToUsdcRate > 0, "KudiSwap: invalid rates");

        owner          = msg.sender;
        USDC           = IERC20(_usdc);
        EURC           = IERC20(_eurc);
        usdcToEurcRate = _usdcToEurcRate;
        eurcToUsdcRate = _eurcToUsdcRate;
    }

    // ── Core Swap Logic ────────────────────────────────────

    /**
     * @notice Swap USDC for EURC at current rate
     * @param amountIn Amount of USDC to swap (6 decimals)
     * @param minAmountOut Minimum EURC to accept (slippage protection)
     * @return amountOut EURC received
     */
    function swapUSDCforEURC(uint256 amountIn, uint256 minAmountOut)
        external
        notPaused
        nonReentrant
        returns (uint256 amountOut)
    {
        require(amountIn > 0, "KudiSwap: zero amount");

        uint256 fee = (amountIn * feeBps) / 10000;
        amountOut   = ((amountIn - fee) * usdcToEurcRate) / 1e6;

        require(amountOut > 0,             "KudiSwap: zero output");
        require(amountOut >= minAmountOut, "KudiSwap: slippage too high");
        require(EURC.balanceOf(address(this)) >= amountOut, "KudiSwap: insufficient EURC");

        // Effects before interactions
        unchecked {
            totalUsdcSwapped   += amountIn;
            totalFeesCollected += fee;
            accruedFees        += fee;
            totalSwaps++;
        }

        USDC.safeTransferFrom(msg.sender, address(this), amountIn);
        EURC.safeTransfer(msg.sender, amountOut);

        emit Swapped(msg.sender, address(USDC), address(EURC), amountIn, amountOut, fee);
    }

    /**
     * @notice Swap EURC for USDC at current rate
     * @param amountIn Amount of EURC to swap (6 decimals)
     * @param minAmountOut Minimum USDC to accept (slippage protection)
     * @return amountOut USDC received
     */
    function swapEURCforUSDC(uint256 amountIn, uint256 minAmountOut)
        external
        notPaused
        nonReentrant
        returns (uint256 amountOut)
    {
        require(amountIn > 0, "KudiSwap: zero amount");

        uint256 fee = (amountIn * feeBps) / 10000;
        amountOut   = ((amountIn - fee) * eurcToUsdcRate) / 1e6;

        require(amountOut > 0,             "KudiSwap: zero output");
        require(amountOut >= minAmountOut, "KudiSwap: slippage too high");
        require(USDC.balanceOf(address(this)) >= amountOut, "KudiSwap: insufficient USDC");

        unchecked {
            totalEurcSwapped   += amountIn;
            totalFeesCollected += fee;
            accruedFees        += fee;
            totalSwaps++;
        }

        EURC.safeTransferFrom(msg.sender, address(this), amountIn);
        USDC.safeTransfer(msg.sender, amountOut);

        emit Swapped(msg.sender, address(EURC), address(USDC), amountIn, amountOut, fee);
    }

    // ── View Functions ─────────────────────────────────────

    /// @notice Preview USDC → EURC swap output
    function previewSwapUSDCtoEURC(uint256 amountIn)
        external view returns (uint256 amountOut, uint256 fee)
    {
        fee       = (amountIn * feeBps) / 10000;
        amountOut = ((amountIn - fee) * usdcToEurcRate) / 1e6;
    }

    /// @notice Preview EURC → USDC swap output
    function previewSwapEURCtoUSDC(uint256 amountIn)
        external view returns (uint256 amountOut, uint256 fee)
    {
        fee       = (amountIn * feeBps) / 10000;
        amountOut = ((amountIn - fee) * eurcToUsdcRate) / 1e6;
    }

    /// @notice Get current pool balances
    function getPoolBalances()
        external view returns (uint256 usdcBalance, uint256 eurcBalance)
    {
        usdcBalance = USDC.balanceOf(address(this));
        eurcBalance = EURC.balanceOf(address(this));
    }

    /// @notice Get full contract stats
    function getStats() external view returns (
        uint256 swaps,
        uint256 usdcSwapped,
        uint256 eurcSwapped,
        uint256 feesCollected,
        uint256 usdcPool,
        uint256 eurcPool
    ) {
        swaps         = totalSwaps;
        usdcSwapped   = totalUsdcSwapped;
        eurcSwapped   = totalEurcSwapped;
        feesCollected = totalFeesCollected;
        usdcPool      = USDC.balanceOf(address(this));
        eurcPool      = EURC.balanceOf(address(this));
    }

    // ── Admin: Rate Timelock ───────────────────────────────

    /**
     * @notice Queue a rate update — effective after RATE_DELAY (5 min)
     * @dev New rate cannot deviate more than 20% from current rate
     *      Prevents instant manipulation and front-running attacks
     * @param _usdcToEurc New USDC→EURC rate * 1e6
     * @param _eurcToUsdc New EURC→USDC rate * 1e6
     */
    function queueRateUpdate(uint256 _usdcToEurc, uint256 _eurcToUsdc)
        external onlyOwner
    {
        require(_usdcToEurc > 0 && _eurcToUsdc > 0, "KudiSwap: invalid rates");

        // No overwrite of existing pending rate
        require(pendingRate.effectiveAt == 0, "KudiSwap: rate update already queued");

        // Absolute rate bounds (can never go below 0.5 or above 2.0)
        require(_usdcToEurc >= MIN_RATE && _usdcToEurc <= MAX_RATE, "KudiSwap: USDC rate absolute bounds");
        require(_eurcToUsdc >= MIN_RATE && _eurcToUsdc <= MAX_RATE, "KudiSwap: EURC rate absolute bounds");

        // Relative bounds: max 20% change from current rate
        uint256 maxUsdc = usdcToEurcRate * (100 + MAX_RATE_CHANGE_PCT) / 100;
        uint256 minUsdc = usdcToEurcRate * (100 - MAX_RATE_CHANGE_PCT) / 100;
        uint256 maxEurc = eurcToUsdcRate * (100 + MAX_RATE_CHANGE_PCT) / 100;
        uint256 minEurc = eurcToUsdcRate * (100 - MAX_RATE_CHANGE_PCT) / 100;

        require(_usdcToEurc <= maxUsdc && _usdcToEurc >= minUsdc, "KudiSwap: USDC rate out of bounds");
        require(_eurcToUsdc <= maxEurc && _eurcToUsdc >= minEurc, "KudiSwap: EURC rate out of bounds");

        pendingRate = PendingRate({
            usdcToEurc:  _usdcToEurc,
            eurcToUsdc:  _eurcToUsdc,
            effectiveAt: block.timestamp + RATE_DELAY
        });

        emit RateUpdateQueued(_usdcToEurc, _eurcToUsdc, pendingRate.effectiveAt);
    }

    /**
     * @notice Cancel a queued rate update
     * @dev Anyone can see the queue — owner can cancel if rate becomes stale
     */
    function cancelRateUpdate() external onlyOwner {
        require(pendingRate.effectiveAt > 0, "KudiSwap: no pending rate");
        delete pendingRate;
    }

    /**
     * @notice Apply queued rate after delay has passed
     * @dev Can be called by anyone — permissionless execution
     */
    function applyRateUpdate() external {
        require(pendingRate.effectiveAt > 0, "KudiSwap: no pending rate");
        require(block.timestamp >= pendingRate.effectiveAt, "KudiSwap: delay not met");

        usdcToEurcRate = pendingRate.usdcToEurc;
        eurcToUsdcRate = pendingRate.eurcToUsdc;
        delete pendingRate;

        emit RateApplied(usdcToEurcRate, eurcToUsdcRate);
    }

    // ── Admin: Liquidity ───────────────────────────────────

    /**
     * @notice Add liquidity to the swap pool
     * @param token USDC or EURC address
     * @param amount Amount to deposit (6 decimals)
     */
    function addLiquidity(address token, uint256 amount)
        external onlyOwner nonReentrant
    {
        require(token == address(USDC) || token == address(EURC), "KudiSwap: unsupported token");
        require(amount > 0, "KudiSwap: zero amount");
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
        emit LiquidityAdded(token, amount);
    }

    /**
     * @notice Queue a withdrawal — effective after 24 hours
     * @dev Prevents instant liquidity removal (rug protection)
     *      Users have 24hrs to see the queued event and act
     * @param token USDC or EURC address
     * @param amount Amount to withdraw
     */
    function queueWithdraw(address token, uint256 amount)
        external onlyOwner
    {
        require(token == address(USDC) || token == address(EURC), "KudiSwap: unsupported token");
        require(amount > 0, "KudiSwap: zero amount");

        uint256 poolBalance = IERC20(token).balanceOf(address(this));
        require(poolBalance >= amount, "KudiSwap: insufficient balance");

        // Max 50% of pool per withdrawal (prevents full drain in one shot)
        require(amount <= poolBalance * MAX_WITHDRAW_PCT / 100, "KudiSwap: exceeds 50% withdrawal cap");

        // Pool must retain minimum liquidity after withdrawal
        require(poolBalance - amount >= MIN_LIQUIDITY, "KudiSwap: below minimum liquidity");

        // No overwrite of pending withdrawal
        require(pendingWithdraw.effectiveAt == 0, "KudiSwap: withdrawal already queued");

        pendingWithdraw = PendingWithdraw({
            token:       token,
            amount:      amount,
            effectiveAt: block.timestamp + WITHDRAW_DELAY
        });

        emit WithdrawQueued(token, amount, pendingWithdraw.effectiveAt);
    }

    /// @notice Cancel a queued withdrawal
    function cancelWithdraw() external onlyOwner {
        require(pendingWithdraw.effectiveAt > 0, "KudiSwap: no pending withdrawal");
        delete pendingWithdraw;
    }

    /**
     * @notice Execute withdrawal after 24 hour delay
     * @dev State cleared BEFORE transfer (CEI pattern)
     */
    function executeWithdraw() external onlyOwner nonReentrant {
        require(pendingWithdraw.effectiveAt > 0, "KudiSwap: no pending withdrawal");
        require(block.timestamp >= pendingWithdraw.effectiveAt, "KudiSwap: delay not met");

        address token  = pendingWithdraw.token;
        uint256 amount = pendingWithdraw.amount;

        // Re-verify min liquidity at execution time (pool may have changed)
        require(
            IERC20(token).balanceOf(address(this)) - amount >= MIN_LIQUIDITY,
            "KudiSwap: below minimum liquidity at execution"
        );

        // Clear state before transfer (CEI)
        delete pendingWithdraw;

        IERC20(token).safeTransfer(owner, amount);
        emit WithdrawExecuted(token, amount, owner);
    }

    // ── Admin: Config ──────────────────────────────────────

    /**
     * @notice Withdraw only accrued protocol fees (separate from liquidity)
     * @dev Fees are tracked separately so owner cannot accidentally drain liquidity
     * @param token USDC or EURC to withdraw fees in
     */
    function withdrawFees(address token) external onlyOwner nonReentrant {
        require(token == address(USDC) || token == address(EURC), "KudiSwap: unsupported token");
        require(accruedFees > 0, "KudiSwap: no fees to withdraw");

        uint256 amount = accruedFees;
        accruedFees    = 0; // clear before transfer

        IERC20(token).safeTransfer(owner, amount);
        emit FeesWithdrawn(token, amount);
    }

    /**
     * @notice Update swap fee
     * @param _feeBps Fee in basis points (max 200 = 2%)
     */
    function updateFee(uint256 _feeBps) external onlyOwner {
        require(_feeBps <= MAX_FEE, "KudiSwap: fee too high");
        emit FeeUpdated(feeBps, _feeBps);
        feeBps = _feeBps;
    }

    /**
     * @notice Pause or unpause swaps
     * @param _paused True to pause, false to unpause
     */
    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PauseToggled(_paused);
    }

    // ── Ownership: Two-Step ────────────────────────────────

    /**
     * @notice Initiate ownership transfer — new owner must accept
     * @param newOwner Address of proposed new owner
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "KudiSwap: zero address");
        require(newOwner != owner,      "KudiSwap: already owner");
        pendingOwner = newOwner;
        emit OwnershipTransferQueued(newOwner);
    }

    /**
     * @notice Accept ownership transfer
     * @dev Must be called by pendingOwner
     */
    function acceptOwnership() external {
        require(msg.sender == pendingOwner, "KudiSwap: not pending owner");
        emit OwnershipTransferred(owner, pendingOwner);
        owner        = pendingOwner;
        pendingOwner = address(0);
    }

    /// @notice Renounce pending ownership (cancel transfer)
    function cancelOwnershipTransfer() external onlyOwner {
        pendingOwner = address(0);
    }
}
