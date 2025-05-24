import { WalletStrategy } from './wallet-strategy.interface';
import { Keypair } from '@solana/web3.js';

export class SolanaWalletStrategy implements WalletStrategy {
  async generateWallet() {
    const keypair = Keypair.generate();
    return {
      address: keypair.publicKey.toString(),
      privateKey: Buffer.from(keypair.secretKey).toString('hex')
    };
  }
} 