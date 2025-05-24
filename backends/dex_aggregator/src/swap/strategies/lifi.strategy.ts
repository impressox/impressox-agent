import { Injectable } from '@nestjs/common';
import { BaseProviderStrategy } from './base-provider.strategy';
import { DexProvider } from '../entities/provider.enum';
import { QuoteResponse } from './provider-strategy.interface';
import { ConfigService } from '@nestjs/config';
import { ethers } from 'ethers';
import { ChainProviderService } from '../services/chain-provider.service';
import { AuthService } from '../../auth/auth.service';
import { TokenService } from '../../token/token.service';
import axios from 'axios';
import { ChainType } from '../../wallet/entities/wallet.entity';

interface LifiQuoteResponse {
  transactionRequest: {
    data: string;
    value: string;
    to: string;
    gasLimit: string;
  };
  estimate: {
    toAmount: string;
    toAmountMin: string;
    approvalAddress?: string;
  };
}

@Injectable()
export class LifiStrategy extends BaseProviderStrategy {
  private readonly LIFI_API_URL: string;
  private readonly LIFI_API_KEY: string;
  private readonly LIFI_INTEGRATOR_ID: string;

  constructor(
    configService: ConfigService,
    private readonly rpcProviderService: ChainProviderService,
    private readonly authService: AuthService,
    private readonly tokenService: TokenService
  ) {
    super(DexProvider.LIFI, configService);
    
    this.LIFI_API_URL = this.configService.get<string>('LIFI_API_URL') || 'https://li.quest/v1/quote';
    this.LIFI_API_KEY = this.configService.get<string>('LIFI_API_KEY');
    this.LIFI_INTEGRATOR_ID = this.configService.get<string>('LIFI_INTEGRATOR_ID') || 'impressox-agent';

    if (!this.LIFI_API_KEY) {
      throw new Error('LIFI_API_KEY is required');
    }
  }

  private async checkAndApproveToken(
    tokenAddress: string,
    spender: string,
    amount: string,
    wallet: ethers.Wallet,
    chainId: number
  ): Promise<void> {
    if (tokenAddress === this.NATIVE_TOKEN) return;

    const tokenContract = new ethers.Contract(
      tokenAddress,
      [
        'function allowance(address,address) view returns (uint256)',
        'function approve(address,uint256) returns (bool)',
        'function decimals() view returns (uint8)'
      ],
      wallet
    );

    const decimals = await tokenContract.decimals();
    const amountWithDecimals = ethers.parseUnits(amount, decimals);
    const currentAllowance = await tokenContract.allowance(await wallet.getAddress(), spender);

    if (currentAllowance < amountWithDecimals) {
      const approveTx = await tokenContract.approve(spender, amountWithDecimals);
      await approveTx.wait();
    }
  }

  async getQuote(
    fromToken: string,
    toToken: string,
    amount: string,
    chainId: number,
    toChainId: number,
    config: Record<string, any>,
  ): Promise<QuoteResponse> {
    try {
      if (!config.userAddress) {
        throw new Error('User address is required for getting quote');
      }

      const params = {
        fromChain: chainId,
        toChain: chainId, // Use same chain for now
        fromToken,
        toToken,
        fromAmount: amount,
        fromAddress: config.userAddress,
        toAddress: config.userAddress,
        integrator: this.LIFI_INTEGRATOR_ID,
        slippage: config.slippage || 0.5,
      };

      const { data } = await axios.get<LifiQuoteResponse>(this.LIFI_API_URL, { 
        params,
        headers: {
          'Authorization': `Bearer ${this.LIFI_API_KEY}`
        }
      });

      if (!data.transactionRequest || !data.estimate) {
        throw new Error('Invalid quote response from LiFi');
      }

      if (!data.estimate.toAmount || !data.estimate.toAmountMin) {
        throw new Error('Missing amount information in quote');
      }

      return {
        fromToken,
        toToken,
        amount,
        fromTokenFee: 0, // Will be set by swap service
        toTokenFee: 0,   // Will be set by swap service
        provider: DexProvider.LIFI,
        expectedOutput: data.estimate.toAmount,
        minimumOutput: data.estimate.toAmountMin,
        txData: {
          data: data.transactionRequest.data,
          value: data.transactionRequest.value || '0',
          to: data.transactionRequest.to,
          gas: data.transactionRequest.gasLimit,
        },
      };
    } catch (error) {
      throw new Error(`Failed to get quote from LiFi: ${error.message}`);
    }
  }

  async executeSwap(
    quote: QuoteResponse,
    walletAddress: string,
    chainId: number
  ): Promise<string> {
    try {
      const provider = await this.rpcProviderService.getProvider(chainId, ChainType.EVM);
      if (!provider) {
        throw new Error('No EVM provider found for executing swap');
      }

      // Get user's private key from auth service
      const privateKey = await this.authService.getUserPrivateKey(walletAddress);
      if (!privateKey) {
        throw new Error('User wallet not found or not authenticated');
      }

      const ethersProvider = provider.getUnderlyingProvider();
      const wallet = new ethers.Wallet(privateKey, ethersProvider);
      
      // Get token decimals
      const fromTokenDecimals = await this.tokenService.getTokenDecimals(quote.fromToken, chainId);

      // Get the DEX router contract address
      const dexRouterAddress = this.getDexRouterAddress(chainId);
      
      // Create contract instance for LifiProxyFacet
      const routerContract = new ethers.Contract(
        dexRouterAddress,
        [
          'function callLifi(uint256 fromTokenWithFee, uint256 fromAmt, uint256 toTokenWithFee, bytes calldata callData) external payable'
        ],
        wallet
      );

      // Parse amounts with correct decimals
      const fromAmount = ethers.parseUnits(quote.amount, fromTokenDecimals);

      // Handle token approvals
      await this.checkAndApproveToken(
        quote.fromToken,
        dexRouterAddress,
        quote.amount,
        wallet,
        chainId
      );

      // Execute swap through the DEX router
      const tx = await routerContract.callLifi(
        BigInt(quote.fromToken),  // fromTokenWithFee (already packed with fee by SwapService)
        fromAmount,               // fromAmt (actual amount to swap)
        BigInt(quote.toToken),    // toTokenWithFee (already packed with fee by SwapService)
        quote.txData.data,        // callData from LiFi
        { value: quote.txData.value }
      );

      return tx.hash;
    } catch (error) {
      throw new Error(`Failed to execute swap: ${error.message}`);
    }
  }
} 