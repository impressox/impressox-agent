import { Injectable } from '@nestjs/common';
import { WalletStrategy } from './wallet-strategy.interface';
import { EvmWalletStrategy } from './evm-wallet.strategy';
import { SolanaWalletStrategy } from './solana-wallet.strategy';
import { ChainType } from '../entities/wallet.entity';

@Injectable()
export class WalletStrategyFactory {
  private strategies: Map<ChainType, WalletStrategy>;

  constructor() {
    this.strategies = new Map();
    this.strategies.set(ChainType.EVM, new EvmWalletStrategy());
    this.strategies.set(ChainType.SOLANA, new SolanaWalletStrategy());
  }

  getStrategy(chainType: ChainType): WalletStrategy {
    const strategy = this.strategies.get(chainType);
    if (!strategy) {
      throw new Error(`No strategy found for chain type: ${chainType}`);
    }
    return strategy;
  }
} 