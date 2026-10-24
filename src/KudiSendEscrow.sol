// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function decimals() external view returns (uint8);
}

library SafeERC20 {
    function safeTransfer(IERC20 token, address to, uint256 amount) internal {
        _call(address(token), abi.encodeWithSelector(token.transfer.selector, to, amount), "SafeERC20: transfer failed");
    }

    function safeTransferFrom(IERC20 token, address from, address to, uint256 amount) internal {
        _call(
            address(token),
            abi.encodeWithSelector(token.transferFrom.selector, from, to, amount),
            "SafeERC20: transferFrom failed"
        );
    }

    function _call(address target, bytes memory data, string memory err) private {
        require(target.code.length > 0, "SafeERC20: not a contract");
        (bool success, bytes memory ret) = target.call(data);
        require(success && (ret.length == 0 || abi.decode(ret, (bool))), err);
    }
}

/// @title KudiSendEscrow
/// @notice Holds stablecoins for a KudiSend payout until it is settled or refunded.
///         Users can always reclaim an untouched deposit after REFUND_DELAY.
contract KudiSendEscrow {
    using SafeERC20 for IERC20;

    // ── Types ──────────────────────────────────────────────
    enum State {
        None,
        Deposited,
        Settled,
        Refunded
    }

    struct Deposit {
        address user;
        address token;
        uint256 amount;
        uint64 time;
        State state;
    }

    // ── Constants ──────────────────────────────────────────
    /// @notice How long a deposit must sit before the depositor can self-refund.
    uint256 public constant REFUND_DELAY = 72 hours;
    /// @notice Max refs per settle call (keeps gas bounded).
    uint256 public constant MAX_BATCH = 100;

    // ── Storage ────────────────────────────────────────────
    address public owner;
    address public pendingOwner;
    address public treasury;
    bool public paused;

    /// @notice Per-deposit limits in token base units (6 decimals).
    uint256 public minDeposit;
    uint256 public maxDeposit;

    mapping(address => bool) public allowedToken;
    address[] public tokenList; // append-only; allowedToken toggles acceptance
    mapping(address => uint256) private _tokenIndexPlusOne;

    mapping(bytes32 => Deposit) public deposits;

    uint256 private _status = 1;

    // ── Events ─────────────────────────────────────────────
    event Deposited(bytes32 indexed ref, address indexed user, address indexed token, uint256 amount);
    event Settled(bytes32 indexed ref, address indexed user, address indexed token, uint256 amount);
    event Refunded(bytes32 indexed ref, address indexed user, address indexed token, uint256 amount, bool byUser);
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event LimitsUpdated(uint256 minDeposit, uint256 maxDeposit);
    event TokenAllowed(address indexed token, bool allowed);
    event PauseToggled(bool paused);
    event OwnershipTransferStarted(address indexed currentOwner, address indexed newOwner);
    event OwnershipTransferred(address indexed oldOwner, address indexed newOwner);

    // ── Modifiers ──────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier nonReentrant() {
        require(_status == 1, "Reentrant call");
        _status = 2;
        _;
        _status = 1;
    }

    // ── Constructor ────────────────────────────────────────
    constructor(
        address owner_,
        address treasury_,
        uint256 minDeposit_,
        uint256 maxDeposit_,
        address[] memory tokens_
    ) {
        require(owner_ != address(0), "Zero owner");
        require(treasury_ != address(0), "Zero treasury");
        owner = owner_;
        treasury = treasury_;
        _setLimits(minDeposit_, maxDeposit_);
        for (uint256 i = 0; i < tokens_.length; i++) {
            _setTokenAllowed(tokens_[i], true);
        }
        emit OwnershipTransferred(address(0), owner_);
    }

    // ── User actions ───────────────────────────────────────

    /**
     * @notice Deposit `amount` of `token` against a backend-issued `ref`.
     * @dev One deposit per ref, ever (even after settle/refund).
     */
    function deposit(address token, uint256 amount, bytes32 ref) external nonReentrant {
        require(!paused, "Paused");
        require(ref != bytes32(0), "Zero ref");
        require(allowedToken[token], "Token not allowed");
        require(amount >= minDeposit, "Below minimum");
        require(amount <= maxDeposit, "Above maximum");
        require(deposits[ref].state == State.None, "Ref used");

        deposits[ref] = Deposit({
            user: msg.sender,
            token: token,
            amount: amount,
            time: uint64(block.timestamp),
            state: State.Deposited
        });

        uint256 balBefore = IERC20(token).balanceOf(address(this));
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
        require(IERC20(token).balanceOf(address(this)) - balBefore == amount, "Inexact transfer");

        emit Deposited(ref, msg.sender, token, amount);
    }

    /**
     * @notice Depositor pulls their own funds back if the deposit is still
     *         untouched after REFUND_DELAY. Works while paused.
     */
    function claimRefund(bytes32 ref) external nonReentrant {
        Deposit storage d = deposits[ref];
        require(d.state == State.Deposited, "Not refundable");
        require(msg.sender == d.user, "Not depositor");
        require(block.timestamp >= uint256(d.time) + REFUND_DELAY, "Too early");

        d.state = State.Refunded;
        IERC20(d.token).safeTransfer(d.user, d.amount);
        emit Refunded(ref, d.user, d.token, d.amount, true);
    }

    // ── Owner actions ──────────────────────────────────────

    /// @notice Mark paid-out deposits as settled and move funds to the treasury.
    function settle(bytes32[] calldata refs) external onlyOwner nonReentrant {
        require(refs.length > 0, "Empty batch");
        require(refs.length <= MAX_BATCH, "Batch too large");

        uint256[] memory sums = new uint256[](tokenList.length);

        for (uint256 i = 0; i < refs.length; i++) {
            Deposit storage d = deposits[refs[i]];
            require(d.state == State.Deposited, "Not settleable");
            d.state = State.Settled;
            sums[_tokenIndexPlusOne[d.token] - 1] += d.amount;
            emit Settled(refs[i], d.user, d.token, d.amount);
        }

        address to = treasury;
        for (uint256 i = 0; i < sums.length; i++) {
            if (sums[i] > 0) IERC20(tokenList[i]).safeTransfer(to, sums[i]);
        }
    }

    /// @notice Return a deposit to its depositor (e.g. payout failed).
    function refund(bytes32 ref) external onlyOwner nonReentrant {
        Deposit storage d = deposits[ref];
        require(d.state == State.Deposited, "Not refundable");

        d.state = State.Refunded;
        IERC20(d.token).safeTransfer(d.user, d.amount);
        emit Refunded(ref, d.user, d.token, d.amount, false);
    }

    /// @notice Pause or unpause NEW deposits. Settle, refund and claimRefund keep working.
    function setPaused(bool paused_) external onlyOwner {
        paused = paused_;
        emit PauseToggled(paused_);
    }

    function setLimits(uint256 minDeposit_, uint256 maxDeposit_) external onlyOwner {
        _setLimits(minDeposit_, maxDeposit_);
    }

    function setTreasury(address treasury_) external onlyOwner {
        require(treasury_ != address(0), "Zero treasury");
        emit TreasuryUpdated(treasury, treasury_);
        treasury = treasury_;
    }

    function setTokenAllowed(address token, bool allowed) external onlyOwner {
        _setTokenAllowed(token, allowed);
    }

    // ── Two-step ownership ─────────────────────────────────
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero owner");
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    function acceptOwnership() external {
        require(msg.sender == pendingOwner, "Not pending owner");
        emit OwnershipTransferred(owner, msg.sender);
        owner = msg.sender;
        pendingOwner = address(0);
    }

    // ── Views ──────────────────────────────────────────────
    function tokenCount() external view returns (uint256) {
        return tokenList.length;
    }

    // ── Internal ───────────────────────────────────────────
    function _setLimits(uint256 minDeposit_, uint256 maxDeposit_) internal {
        require(minDeposit_ > 0 && minDeposit_ <= maxDeposit_, "Bad limits");
        minDeposit = minDeposit_;
        maxDeposit = maxDeposit_;
        emit LimitsUpdated(minDeposit_, maxDeposit_);
    }

    function _setTokenAllowed(address token, bool allowed) internal {
        require(token != address(0), "Zero token");
        if (allowed) {
            require(token.code.length > 0, "Not a contract");
            require(IERC20(token).decimals() == 6, "Token must be 6 decimals");
            if (_tokenIndexPlusOne[token] == 0) {
                tokenList.push(token);
                _tokenIndexPlusOne[token] = tokenList.length;
            }
        }
        allowedToken[token] = allowed;
        emit TokenAllowed(token, allowed);
    }
}
