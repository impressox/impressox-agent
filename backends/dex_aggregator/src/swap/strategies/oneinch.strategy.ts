import { Injectable, BadRequestException } from '@nestjs/common';
import axios from 'axios';
import { DexProvider } from '../entities/provider.enum';
import { BaseProviderStrategy } from './base-provider.strategy';
import { QuoteResponse } from './provider-strategy.interface';
import { ConfigService } from '@nestjs/config';
import { ethers } from 'ethers';
import { ChainProviderService } from '../services/chain-provider.service';
import { AuthService } from '../../auth/auth.service';
import { TokenService } from '../../token/token.service';
import { ChainType } from '../../wallet/entities/wallet.entity';

interface OneInchQuoteResponse {
  toTokenAmount: string;
  tx: {
    data: string;
    value: string;
    to: string;
    gas: string;
  };
}

@Injectable()
export class OneInchStrategy extends BaseProviderStrategy {
  private readonly ONEINCH_API_URL: string;
  private readonly ONEINCH_API_KEY: string;

  constructor(
    configService: ConfigService,
    private readonly rpcProviderService: ChainProviderService,
    private readonly authService: AuthService,
    private readonly tokenService: TokenService
  ) {
    super(DexProvider.ONEINCH, configService);
    
    this.ONEINCH_API_URL = this.configService.get<string>('ONEINCH_API_URL') || 'https://api.1inch.io/v5.2';
    this.ONEINCH_API_KEY = this.configService.get<string>('ONEINCH_API_KEY');

    if (!this.ONEINCH_API_KEY) {
      throw new Error('ONEINCH_API_KEY is required');
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

      const dexRouterAddress = this.getDexRouterAddress(chainId);
      const gasPrice = await this.getGasPrice(chainId);

      const { data } = await axios.get<OneInchQuoteResponse>(
        `${this.ONEINCH_API_URL}/swap/v5.2/${chainId}/swap`,
        {
          headers: {
            'Authorization': `Bearer ${this.ONEINCH_API_KEY}`,
            'Accept': 'application/json'
          },
          params: {
            fromTokenAddress: fromToken,
            toTokenAddress: toToken,
            amount,
            fromAddress: config.userAddress,
            slippage: config.slippage || 1,
            disableEstimate: true,
            protocols: 'UNISWAP_V3,UNISWAP_V2,SUSHISWAP,CURVE,1INCH_LIMIT_ORDER_PROTOCOL',
            gasPrice,
          },
        }
      );

      if (!data.tx || !data.toTokenAmount) {
        throw new Error('Invalid quote response from 1inch');
      }

      return {
        fromToken,
        toToken,
        amount,
        fromTokenFee: 0, // Will be set by swap service
        toTokenFee: 0,   // Will be set by swap service
        provider: DexProvider.ONEINCH,
        txData: {
          data: data.tx.data,
          value: data.tx.value || '0',
          to: data.tx.to,
          gas: data.tx.gas,
        },
        expectedOutput: data.toTokenAmount,
        minimumOutput: data.toTokenAmount, // 1inch handles slippage internally
      };
    } catch (error) {
      throw new BadRequestException(`Failed to get 1inch quote: ${error.message}`);
    }
  }

  private async getGasPrice(chainId: number): Promise<string> {
    const provider = await this.rpcProviderService.getProvider(chainId, ChainType.EVM);
    if (!provider) {
      throw new BadRequestException(`No EVM provider found for chain ID ${chainId}`);
    }
    const ethersProvider = provider.getUnderlyingProvider();
    const feeData = await ethersProvider.getFeeData();
    return feeData.gasPrice?.toString() || '0';
  }

  async executeSwap(
    quote: QuoteResponse,
    walletAddress: string,
    chainId: number
  ): Promise<string> {
    try {
      const provider = await this.rpcProviderService.getProvider(chainId, ChainType.EVM);
      if (!provider) {
        throw new BadRequestException(`No EVM provider found for chain ID ${chainId}`);
      }

      // Get user's private key from auth service
      const privateKey = await this.authService.getUserPrivateKey(walletAddress);
      if (!privateKey) {
        throw new BadRequestException('User wallet not found or not authenticated');
      }

      const ethersProvider = provider.getUnderlyingProvider();
      const wallet = new ethers.Wallet(privateKey, ethersProvider);
      
      // Get token decimals
      const fromTokenDecimals = await this.tokenService.getTokenDecimals(quote.fromToken, chainId);

      // Get the DEX router contract address
      const routerAddress = this.getDexRouterAddress(chainId);
      
      // Create contract instance for OneInchProxyFacet
      const routerContract = new ethers.Contract(
        routerAddress,
        [
          'function callOneInch(uint256 fromTokenWithFee, uint256 fromAmt, uint256 toTokenWithFee, bytes calldata callData) external payable'
        ],
        wallet
      );

      // Parse amounts with correct decimals
      const fromAmount = ethers.parseUnits(quote.amount, fromTokenDecimals);

      // Handle token approvals
      await this.checkAndApproveToken(
        quote.fromToken,
        routerAddress,
        quote.amount,
        wallet,
        chainId
      );

      // Execute swap through the DEX router
      const tx = await routerContract.callOneInch(
        BigInt(quote.fromToken),  // fromTokenWithFee (already packed with fee by SwapService)
        fromAmount,               // fromAmt (actual amount to swap)
        BigInt(quote.toToken),    // toTokenWithFee (already packed with fee by SwapService)
        quote.txData.data,        // callData from 1inch
        { value: quote.txData.value }
      );

      return tx.hash;
    } catch (error) {
      throw new BadRequestException(`Failed to execute swap: ${error.message}`);
    }
  }
} 