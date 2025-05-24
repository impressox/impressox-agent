import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DexProvider } from '../entities/provider.enum';
import { ProviderStrategy, QuoteResponse } from './provider-strategy.interface';

@Injectable()
export abstract class BaseProviderStrategy implements ProviderStrategy {
  protected readonly NATIVE_TOKEN = '0x0000000000000000000000000000000000000000';

  constructor(
    protected readonly provider: DexProvider,
    protected readonly configService: ConfigService,
  ) {}

  getProvider(): DexProvider {
    return this.provider;
  }

  protected getDexRouterAddress(chainId: number): string {
    const routerAddress = this.configService.get<string>(`${this.provider}_ROUTER_ADDRESS_${chainId}`);
    if (!routerAddress) {
      throw new Error(`No router address configured for ${this.provider} on chain ${chainId}`);
    }
    return routerAddress;
  }

  abstract getQuote(
    fromToken: string,
    toToken: string,
    amount: string,
    fromChainId: number,
    toChainId: number,
    config: Record<string, any>,
  ): Promise<QuoteResponse>;

  abstract executeSwap(
    quote: QuoteResponse,
    walletAddress: string,
    fromChainId: number
  ): Promise<string>;

  protected validateConfig(config: any, requiredKeys: string[]): void {
    for (const key of requiredKeys) {
      if (!config[key]) {
        throw new Error(`Missing required config key: ${key}`);
      }
    }
  }
} 