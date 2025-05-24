import { Injectable, BadRequestException, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TokenService } from '../token/token.service';
import { ChainType } from '../wallet/entities/wallet.entity';
import { ChainProviderService } from './services/chain-provider.service';
import { ProviderStrategy, QuoteResponse } from './strategies/provider-strategy.interface';
import { DexProvider } from './entities/provider.enum';
import { OneInchStrategy } from './strategies/oneinch.strategy';
import { LifiStrategy } from './strategies/lifi.strategy';
import { SwapRequestDto } from './dto/swap-request.dto';
import { WalletService } from '../wallet/wallet.service';
import { GetQuoteRequest } from './dto/get-quote-request.dto';

@Injectable()
export class SwapService {
  private readonly strategies: Map<DexProvider, ProviderStrategy>;
  private readonly NATIVE_TOKEN_ADDRESS = '0x0000000000000000000000000000000000000000';
  private readonly logger = new Logger(SwapService.name);
  private readonly MAX_RETRIES = 3;
  private readonly RETRY_DELAY = 1000; // 1 second

  constructor(
    private readonly configService: ConfigService,
    private readonly tokenService: TokenService,
    private readonly chainProviderService: ChainProviderService,
    private readonly oneInchStrategy: OneInchStrategy,
    private readonly lifiStrategy: LifiStrategy,
    private readonly walletService: WalletService,
  ) {
    this.strategies = new Map();
    this.strategies.set(oneInchStrategy.getProvider(), oneInchStrategy);
    this.strategies.set(lifiStrategy.getProvider(), lifiStrategy);
  }

  private async sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private async retry<T>(
    operation: () => Promise<T>,
    operationName: string,
    maxRetries: number = this.MAX_RETRIES
  ): Promise<T> {
    let lastError: Error;
    for (let i = 0; i < maxRetries; i++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        this.logger.warn(
          `Attempt ${i + 1}/${maxRetries} failed for ${operationName}: ${error.message}`
        );
        if (i < maxRetries - 1) {
          await this.sleep(this.RETRY_DELAY * Math.pow(2, i)); // Exponential backoff
        }
      }
    }
    throw lastError;
  }

  async processSwapRequest(request: GetQuoteRequest, userId?: string): Promise<QuoteResponse> {
    const { fromToken, toToken, amount, provider, platform } = request;

    // Validate request
    if (!fromToken || !toToken || !amount) {
      throw new BadRequestException('Missing required parameters');
    }

    // Get chain info
    const chain = await this.chainProviderService.resolveTokenChain(fromToken);

    // Get provider strategy
    const strategy = this.strategies.get(provider);
    if (!strategy) {
      throw new BadRequestException(`Unsupported provider: ${provider}`);
    }

    // Get quote
    const quote = await strategy.getQuote(
      fromToken,
      toToken,
      amount,
      chain.chainId,
      chain.chainId, // Use same chain for now
      {
        userAddress: request.walletAddress,
        slippage: request.slippage || 0.5,
        platform
      }
    );

    return quote;
  }

  private calculateAmountAfterFee(amount: string, fee: number): string {
    const amountBigInt = BigInt(amount);
    const feeAmount = (amountBigInt * BigInt(Math.floor(fee * 100))) / BigInt(10000);
    return (amountBigInt - feeAmount).toString();
  }

  async getBestQuote(
    fromToken: string,
    toToken: string,
    amount: string,
    fromChainType: ChainType,
    fromChainId: number,
    toChainType: ChainType,
    toChainId: number,
    walletAddress: string,
  ): Promise<QuoteResponse> {
    return this.retry(async () => {
      this.logger.debug('Getting best quote', {
        fromToken,
        toToken,
        amount,
        fromChainType,
        fromChainId,
        toChainType,
        toChainId,
        walletAddress,
      });

      // Get providers for the chain ID
      const providers = await this.chainProviderService.getProvidersByChainId(fromChainId);
      if (providers.length === 0) {
        throw new BadRequestException(`No active providers found for chain ID ${fromChainId}`);
      }

      this.logger.debug(`Found ${providers.length} providers for chain ${fromChainId}`, {
        providers: providers.map(p => ({
          provider: p.provider,
          priority: p.priority
        }))
      });

      // Get quotes from all providers
      const quotePromises = providers.map(async (provider) => {
        const strategy = this.strategies.get(provider.provider);
        if (!strategy) {
          this.logger.warn(`No strategy found for provider ${provider.provider}`);
          return null;
        }

        try {
          this.logger.debug(`Getting quote from ${provider.provider}`, {
            fromChainId,
            toChainId,
            priority: provider.priority
          });

          const quote = await strategy.getQuote(
            fromToken,
            toToken,
            amount,
            fromChainId,
            toChainId,
            {
              ...provider.config,
              userAddress: walletAddress,
              slippage: provider.config?.slippage || 0.5,
            }
          );

          this.logger.debug(`Got quote from ${provider.provider}`, {
            expectedOutput: quote.expectedOutput,
            provider: provider.provider
          });

          return quote;
        } catch (error) {
          this.logger.error(`Error getting quote from ${provider.provider}:`, error);
          return null;
        }
      });

      const quotes = (await Promise.all(quotePromises)).filter(Boolean);

      if (quotes.length === 0) {
        throw new BadRequestException('No valid quotes available');
      }

      // Get token fees
      const defaultFee = this.configService.get<number>('DEFAULT_TOKEN_FEE', 0.5);
      const fromTokenFee = await this.tokenService.getTokenFee(fromToken, fromChainType, fromChainId) ?? defaultFee;
      const toTokenFee = await this.tokenService.getTokenFee(toToken, toChainType, toChainId) ?? defaultFee;

      // Calculate amounts after fees
      const amountAfterFee = this.calculateAmountAfterFee(amount, fromTokenFee);

      // Get the best quote (highest output amount)
      const bestQuote = quotes.reduce((best, current) => {
        const bestOutput = BigInt(best.expectedOutput);
        const currentOutput = BigInt(current.expectedOutput);
        return currentOutput > bestOutput ? current : best;
      });

      // Pack tokens with fees
      const fromTokenWithFee = this.packTokenWithFee(fromToken, fromTokenFee);
      const toTokenWithFee = this.packTokenWithFee(toToken, toTokenFee);

      return {
        ...bestQuote,
        fromToken: fromTokenWithFee,
        toToken: toTokenWithFee,
        amount: amountAfterFee,
        fromTokenFee,
        toTokenFee,
      };
    }, 'getBestQuote');
  }

  private packTokenWithFee(address: string, fee: number): string {
    const feeInt = Math.floor(fee * 100);
    const packedFee = feeInt.toString(16).padStart(4, '0');
    return `0x${packedFee}${address.slice(2)}`;
  }

  async executeSwap(
    quote: QuoteResponse,
    walletAddress: string,
    chainType: ChainType,
    chainId: number
  ): Promise<string> {
    const strategy = this.strategies.get(quote.provider);
    if (!strategy) {
      throw new BadRequestException(`Unsupported provider: ${quote.provider}`);
    }

    return strategy.executeSwap(quote, walletAddress, chainId);
  }
} 