import 'dotenv/config.js';
import { ethers } from 'ethers';
import axios from 'axios';

// Kết nối tới node fork local
const provider = new ethers.JsonRpcProvider('http://127.0.0.1:8545');
const PRIVATE_KEY = process.env.USER_PRIVATE_KEY;
const DIAMOND_ADDRESS = process.env.DIAMOND_ADDRESS;

// Token addresses for Base
const TOKENS = {
    WETH: "0x4200000000000000000000000000000000000006",
    USDC: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    USDT: "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    DAI: "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    NEW_TOKEN: "0xbf8566956b4e2D8BEB90c4c19dbb8c67A9290C36"
};

async function approveToken(token, spender, amount, tokenName, signer) {
    const currentAllowance = await token.allowance(await signer.getAddress(), spender);
    console.log(`Current allowance for ${tokenName}:`, ethers.formatUnits(currentAllowance, await token.decimals()));
    
    if (currentAllowance < amount) {
        console.log(`Approving ${tokenName} for ${spender}...`);
        const approveTx = await token.approve(spender, amount);
        await approveTx.wait();
        console.log(`${tokenName} approved for ${spender}`);
    }
}

async function swapEthToToken(fromAmount, toToken, tokenName) {
    const signer = new ethers.Wallet(PRIVATE_KEY, provider);
    console.log(`\nTesting ETH -> ${tokenName} swap...`);
    
    const fromToken = "0x0000000000000000000000000000000000000000"; // ETH

    // 1. Get quote from LiFi API
    const lifiQuoteEndpoint = "https://li.quest/v1/quote";
    const params = {
        fromChain: 8453,
        toChain: 8453,
        fromToken,
        toToken,
        fromAmount: fromAmount.toString(),
        fromAddress: await signer.getAddress(),
        toAddress: await signer.getAddress(),
        integrator: "impressox-agent",
        slippage: 0.5, // 0.5% slippage
    };

    console.log("Getting quote from LiFi...");
    const { data } = await axios.get(lifiQuoteEndpoint, { params });
    if (!data.transactionRequest || !data.estimate || !data.estimate.approvalAddress) {
        throw new Error("LiFi quote API missing information!");
    }
    const { transactionRequest } = data;
    console.log("Quote received from LiFi");

    // 2. Check ETH balance
    const balance = await provider.getBalance(await signer.getAddress());
    console.log("ETH balance:", ethers.formatEther(balance));
    if (balance < fromAmount) {
        throw new Error("Insufficient ETH balance");
    }

    // 3. Call Diamond contract (LifiProxyFacet)
    const diamondAbi = [
        "function callLifi(uint256,uint256,uint256,bytes) external payable"
    ];
    const diamond = new ethers.Contract(DIAMOND_ADDRESS, diamondAbi, signer);

    const fromTokenWithFee = BigInt(fromToken).toString();
    const toTokenWithFee = BigInt(toToken).toString();
    const callData = transactionRequest.data;
    const value = transactionRequest.value || "0";

    console.log("Executing swap...");
    const tx = await diamond.callLifi(
        fromTokenWithFee,
        fromAmount,
        toTokenWithFee,
        callData,
        { value }
    );
    console.log("Transaction sent:", tx.hash);
    const receipt = await tx.wait();
    console.log("Transaction successful!");
    console.log("Gas used:", receipt.gasUsed.toString());

    // 4. Check token balance after swap
    const erc20Abi = [
        "function balanceOf(address) external view returns (uint256)",
        "function decimals() external view returns (uint8)"
    ];
    const token = new ethers.Contract(toToken, erc20Abi, provider);
    const decimals = await token.decimals();
    const tokenBalance = await token.balanceOf(await signer.getAddress());
    console.log(`${tokenName} balance after swap:`, ethers.formatUnits(tokenBalance, decimals));
    
    return { token, decimals, tokenBalance };
}

async function swapTokenToEth(fromToken, tokenName) {
    const signer = new ethers.Wallet(PRIVATE_KEY, provider);
    console.log(`\nTesting ${tokenName} -> ETH swap...`);

    const toToken = "0x0000000000000000000000000000000000000000"; // ETH

    // 1. Get token balance and decimals
    const erc20Abi = [
        "function balanceOf(address) external view returns (uint256)",
        "function decimals() external view returns (uint8)",
        "function approve(address,uint256) external returns (bool)",
        "function allowance(address,address) external view returns (uint256)"
    ];
    const token = new ethers.Contract(fromToken, erc20Abi, signer);
    const decimals = await token.decimals();
    const tokenBalance = await token.balanceOf(await signer.getAddress());
    console.log(`${tokenName} balance:`, ethers.formatUnits(tokenBalance, decimals));

    if (tokenBalance === 0n) {
        throw new Error(`No ${tokenName} balance to swap`);
    }

    const swapAmount = tokenBalance;
    console.log(`Using ${ethers.formatUnits(swapAmount, decimals)} ${tokenName} for swap`);

    // 2. Get quote from LiFi API
    const lifiQuoteEndpoint = "https://li.quest/v1/quote";
    const params = {
        fromChain: 8453,
        toChain: 8453,
        fromToken,
        toToken,
        fromAmount: swapAmount.toString(),
        fromAddress: await signer.getAddress(),
        toAddress: await signer.getAddress(),
        integrator: "impressox-agent",
        slippage: 0.5, // 0.5% slippage
    };

    console.log("Getting quote from LiFi...");
    const { data } = await axios.get(lifiQuoteEndpoint, { params });
    if (!data.transactionRequest || !data.estimate) {
        console.error("LiFi API response:", data);
        throw new Error("LiFi quote API missing information!");
    }
    const { transactionRequest, estimate } = data;
    console.log("Quote received from LiFi");
    console.log("Expected output amount:", estimate.toAmount);
    console.log("Minimum output amount:", estimate.toAmountMin);

    if (!estimate.toAmount || !estimate.toAmountMin) {
        throw new Error("Invalid quote from LiFi - missing amount information");
    }

    // 3. Approve token for both Diamond contract and LiFi router
    await approveToken(token, DIAMOND_ADDRESS, swapAmount, tokenName, signer);
    if (data.estimate.approvalAddress) {
        await approveToken(token, data.estimate.approvalAddress, swapAmount, tokenName, signer);
    }

    // 4. Call Diamond contract (LifiProxyFacet)
    const diamondAbi = [
        "function callLifi(uint256,uint256,uint256,bytes) external payable"
    ];
    const diamond = new ethers.Contract(DIAMOND_ADDRESS, diamondAbi, signer);

    const fromTokenWithFee = BigInt(fromToken).toString();
    const toTokenWithFee = BigInt(toToken).toString();
    const callData = transactionRequest.data;
    const value = transactionRequest.value || "0";

    console.log("Executing swap...");
    console.log("From amount:", ethers.formatUnits(swapAmount, decimals));
    console.log("Value:", ethers.formatEther(value));
    console.log("Expected output:", ethers.formatEther(estimate.toAmount));
    console.log("Minimum output:", ethers.formatEther(estimate.toAmountMin));

    // Get initial ETH balance
    const initialEthBalance = await provider.getBalance(await signer.getAddress());
    console.log("Initial ETH balance:", ethers.formatEther(initialEthBalance));

    const tx = await diamond.callLifi(
        fromTokenWithFee,
        swapAmount,
        toTokenWithFee,
        callData,
        { value }
    );
    console.log("Transaction sent:", tx.hash);
    const receipt = await tx.wait();
    console.log("Transaction successful!");
    console.log("Gas used:", receipt.gasUsed.toString());

    // Parse events from receipt
    const diamondInterface = new ethers.Interface([
        "event TokensTransferred(address indexed token, address indexed to, uint256 amount)",
        "event FeeCollected(address indexed token, address indexed recipient, uint256 amount)"
    ]);

    let totalFeeAmount = 0n;
    let totalTransferredAmount = 0n;

    for (const log of receipt.logs) {
        try {
            const parsedLog = diamondInterface.parseLog(log);
            if (parsedLog.name === "FeeCollected") {
                const [token, recipient, amount] = parsedLog.args;
                if (token.toLowerCase() === fromToken.toLowerCase()) {
                    totalFeeAmount += amount;
                    console.log(`Fee collected: ${ethers.formatUnits(amount, decimals)} ${tokenName}`);
                }
            } else if (parsedLog.name === "TokensTransferred") {
                const [token, to, amount] = parsedLog.args;
                if (token.toLowerCase() === fromToken.toLowerCase() && to.toLowerCase() === await signer.getAddress()) {
                    totalTransferredAmount += amount;
                    console.log(`Tokens transferred: ${ethers.formatUnits(amount, decimals)} ${tokenName}`);
                }
            }
        } catch (e) {
            // Skip logs that can't be parsed
            continue;
        }
    }

    // Calculate actual received amount
    const finalEthBalance = await provider.getBalance(await signer.getAddress());
    const actualReceived = finalEthBalance - initialEthBalance + BigInt(receipt.gasUsed) * BigInt(receipt.gasPrice);
    console.log("Actual received ETH:", ethers.formatEther(actualReceived));
    console.log("Final ETH balance:", ethers.formatEther(finalEthBalance));

    // Get token balance after swap
    const tokenBalanceAfterSwap = await token.balanceOf(await signer.getAddress());
    const actualSwapped = tokenBalance - tokenBalanceAfterSwap;
    console.log("Actual swapped token amount:", ethers.formatUnits(actualSwapped, decimals));
    console.log("Token balance after swap:", ethers.formatUnits(tokenBalanceAfterSwap, decimals));
    console.log("Total fee amount:", ethers.formatUnits(totalFeeAmount, decimals));
    console.log("Total transferred amount:", ethers.formatUnits(totalTransferredAmount, decimals));
}

async function main() {
    // Get signer
    const signer = new ethers.Wallet(PRIVATE_KEY, provider);
    console.log("Using wallet address:", await signer.getAddress());

    // Swap ETH to USDC
    await swapEthToToken(
        ethers.parseEther("0.01"), // 0.01 ETH
        TOKENS.USDC,
        "USDC"
    );

    // Swap ETH to new token
    await swapEthToToken(
        ethers.parseEther("0.01"), // 0.01 ETH
        TOKENS.NEW_TOKEN,
        "NEW_TOKEN"
    );

    // Swap USDC back to ETH
    await swapTokenToEth(TOKENS.USDC, "USDC");

    // Swap new token back to ETH
    await swapTokenToEth(TOKENS.NEW_TOKEN, "NEW_TOKEN");
}

// Run main function
main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    }); 