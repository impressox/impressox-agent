export interface WalletStrategy {
  generateWallet(): Promise<{
    address: string;
    privateKey: string;
    mnemonic?: string;
  }>;
} 