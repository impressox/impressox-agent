import { DexProvider } from '../entities/provider.enum';

export interface QuoteResponse {
  fromToken: string;
  toToken: string;
  amount: string;  // Single amount for swap
  fromTokenFee: number;
  toTokenFee: number;
  provider: DexProvider;
  expectedOutput: string;  // Expected output amount
  minimumOutput: string;   // Minimum output amount after slippage
  txData: {
    data: string;
    value: string;
    to: string;
    gas: string;
  };
}

export interface ProviderStrategy {
  getProvider(): DexProvider;
  getQuote(
    fromToken: string,
    toToken: string,
    amount: string,
    chainId: number,
    toChainId: number,
    config: Record<string, any>,
  ): Promise<QuoteResponse>;
  executeSwap(
    quote: QuoteResponse,
    walletAddress: string,
    chainId: number
  ): Promise<string>;
} 