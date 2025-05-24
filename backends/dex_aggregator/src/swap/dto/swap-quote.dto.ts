export class SwapQuoteDto {
  provider: string;
  fromToken: string;
  toToken: string;
  fromAmount: string;
  toAmount: string;
  price: string;
  priceImpact: string;
  gasEstimate: string;
  transaction: {
    data: string;
    value: string;
    to: string;
    gas: string;
  };
} 