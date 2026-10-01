// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function decimals() external view returns (uint8);
}

contract KudiSwap {
    address public owner;
    bool    public paused;
    address public constant USDC = 0x3600000000000000000000000000000000000000;
    address public constant EURC = 0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a;
    uint256 public usdcToEurcRate;
    uint256 public eurcToUsdcRate;
    uint256 public feeBps = 30;
    uint256 public totalUsdcSwapped;
    uint256 public totalEurcSwapped;
    uint256 public totalSwaps;

    event Swapped(address indexed user, address indexed fromToken, address indexed toToken, uint256 amountIn, uint256 amountOut, uint256 fee);
    event RateUpdated(uint256 usdcToEurc, uint256 eurcToUsdc, uint256 timestamp);
    event LiquidityAdded(address token, uint256 amount);
    event LiquidityWithdrawn(address token, uint256 amount);
    event Paused(bool status);

    modifier onlyOwner() { require(msg.sender == owner, "KudiSwap: not owner"); _; }
    modifier notPaused() { require(!paused, "KudiSwap: contract is paused"); _; }

    constructor(uint256 _usdcToEurcRate, uint256 _eurcToUsdcRate) {
        owner = msg.sender;
        usdcToEurcRate = _usdcToEurcRate;
        eurcToUsdcRate = _eurcToUsdcRate;
    }

    function swapUSDCforEURC(uint256 amountIn, uint256 minAmountOut) external notPaused returns (uint256 amountOut) {
        require(amountIn > 0, "KudiSwap: amount must be > 0");
        uint256 fee = (amountIn * feeBps) / 10000;
        amountOut = ((amountIn - fee) * usdcToEurcRate) / 1e6;
        require(amountOut >= minAmountOut, "KudiSwap: slippage too high");
        require(IERC20(EURC).balanceOf(address(this)) >= amountOut, "KudiSwap: insufficient EURC liquidity");
        require(IERC20(USDC).transferFrom(msg.sender, address(this), amountIn), "KudiSwap: USDC transfer failed");
        require(IERC20(EURC).transfer(msg.sender, amountOut), "KudiSwap: EURC transfer failed");
        totalUsdcSwapped += amountIn;
        totalSwaps++;
        emit Swapped(msg.sender, USDC, EURC, amountIn, amountOut, fee);
    }

    function swapEURCforUSDC(uint256 amountIn, uint256 minAmountOut) external notPaused returns (uint256 amountOut) {
        require(amountIn > 0, "KudiSwap: amount must be > 0");
        uint256 fee = (amountIn * feeBps) / 10000;
        amountOut = ((amountIn - fee) * eurcToUsdcRate) / 1e6;
        require(amountOut >= minAmountOut, "KudiSwap: slippage too high");
        require(IERC20(USDC).balanceOf(address(this)) >= amountOut, "KudiSwap: insufficient USDC liquidity");
        require(IERC20(EURC).transferFrom(msg.sender, address(this), amountIn), "KudiSwap: EURC transfer failed");
        require(IERC20(USDC).transfer(msg.sender, amountOut), "KudiSwap: USDC transfer failed");
        totalEurcSwapped += amountIn;
        totalSwaps++;
        emit Swapped(msg.sender, EURC, USDC, amountIn, amountOut, fee);
    }

    function previewSwapUSDCtoEURC(uint256 amountIn) external view returns (uint256 amountOut, uint256 fee) {
        fee = (amountIn * feeBps) / 10000;
        amountOut = ((amountIn - fee) * usdcToEurcRate) / 1e6;
    }

    function previewSwapEURCtoUSDC(uint256 amountIn) external view returns (uint256 amountOut, uint256 fee) {
        fee = (amountIn * feeBps) / 10000;
        amountOut = ((amountIn - fee) * eurcToUsdcRate) / 1e6;
    }

    function getPoolBalances() external view returns (uint256 usdcBalance, uint256 eurcBalance) {
        usdcBalance = IERC20(USDC).balanceOf(address(this));
        eurcBalance = IERC20(EURC).balanceOf(address(this));
    }

    function updateRates(uint256 _usdcToEurc, uint256 _eurcToUsdc) external onlyOwner {
        require(_usdcToEurc > 0 && _eurcToUsdc > 0, "KudiSwap: invalid rates");
        usdcToEurcRate = _usdcToEurc;
        eurcToUsdcRate = _eurcToUsdc;
        emit RateUpdated(_usdcToEurc, _eurcToUsdc, block.timestamp);
    }

    function updateFee(uint256 _feeBps) external onlyOwner {
        require(_feeBps <= 200, "KudiSwap: fee too high");
        feeBps = _feeBps;
    }

    function addLiquidity(address token, uint256 amount) external onlyOwner {
        require(token == USDC || token == EURC, "KudiSwap: unsupported token");
        require(IERC20(token).transferFrom(msg.sender, address(this), amount), "KudiSwap: transfer failed");
        emit LiquidityAdded(token, amount);
    }

    function withdrawLiquidity(address token, uint256 amount) external onlyOwner {
        require(token == USDC || token == EURC, "KudiSwap: unsupported token");
        require(IERC20(token).transfer(owner, amount), "KudiSwap: transfer failed");
        emit LiquidityWithdrawn(token, amount);
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit Paused(_paused);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "KudiSwap: zero address");
        owner = newOwner;
    }
}
