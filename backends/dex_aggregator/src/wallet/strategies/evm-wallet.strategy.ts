import { WalletStrategy } from './wallet-strategy.interface';
import { ethers } from 'ethers';

export class EvmWalletStrategy implements WalletStrategy {
  async generateWallet() {
    const wallet = ethers.Wallet.createRandom();
    return {
      address: wallet.address,
      privateKey: wallet.privateKey,
      mnemonic: wallet.mnemonic?.phrase
    };
  }
} 