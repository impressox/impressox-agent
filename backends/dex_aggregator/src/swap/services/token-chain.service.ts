import { Injectable, BadRequestException, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TokenService } from '../../token/token.service';
import { ChainType } from '../../wallet/entities/wallet.entity';
import { ethers } from 'ethers';
import { Connection, PublicKey } from '@solana/web3.js';
import { isValidSuiAddress } from '@mysten/sui.js/utils';
import { AptosAccount } from 'aptos';

@Injectable()
export class TokenChainService {
  private readonly solanaConnection: Connection | null = null;
  private readonly logger = new Logger(TokenChainService.name);

  constructor(private readonly configService: ConfigService) {
    const solanaRpcUrl = this.configService.get<string>('SOLANA_RPC_URL');
    if (solanaRpcUrl) {
      try {
        this.solanaConnection = new Connection(solanaRpcUrl);
      } catch (error) {
        this.logger.warn(`Failed to initialize Solana connection: ${error.message}`);
      }
    }
  }

  async detectChainTypeFromAddress(address: string): Promise<ChainType | null> {
    try {
      // Check EVM address first (most common)
      if (this.isValidEVMAddress(address)) {
        return ChainType.EVM;
      }

      // Check Solana address
      if (this.solanaConnection && await this.isValidSolanaAddress(address)) {
        return ChainType.SOLANA;
      }

      // Check Move-based chains (Sui and Aptos)
      if (this.isValidMoveAddress(address)) {
        // For Move addresses, we need additional context to determine the chain
        // This could come from:
        // 1. Chain ID if provided
        // 2. Token contract address format
        // 3. RPC endpoint response
        // For now, we'll return MOVE type and let the caller determine the specific chain
        return ChainType.MOVE;
      }

      return null;
    } catch (error) {
      this.logger.error(`Error detecting chain type for address ${address}:`, error);
      return null;
    }
  }

  private isValidEVMAddress(address: string): boolean {
    try {
      // Check if it's a valid hex address
      if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
        return false;
      }

      // Check checksum using ethers
      return ethers.isAddress(address);
    } catch (error) {
      return false;
    }
  }

  private async isValidSolanaAddress(address: string): Promise<boolean> {
    try {
      if (!this.solanaConnection) {
        return false;
      }

      // Check if it's a valid base58 string
      if (!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(address)) {
        return false;
      }

      // Try to create a PublicKey
      const publicKey = new PublicKey(address);
      
      // Verify the account exists
      const accountInfo = await this.solanaConnection.getAccountInfo(publicKey);
      return accountInfo !== null;
    } catch (error) {
      return false;
    }
  }

  private isValidMoveAddress(address: string): boolean {
    try {
      // Check if it's a valid hex address (32 bytes = 64 hex chars)
      if (!/^0x[a-fA-F0-9]{64}$/.test(address)) {
        return false;
      }

      // Try to create an AptosAccount to validate format
      new AptosAccount(Buffer.from(address.slice(2), 'hex'));
      return true;
    } catch (error) {
      return false;
    }
  }

  async validateTokens(fromToken: string, toToken: string): Promise<void> {
    // Check if tokens are the same
    if (fromToken === toToken) {
      throw new BadRequestException('Cannot swap the same token');
    }

    // Check if both are native tokens
    const fromTokenType = await this.detectChainTypeFromAddress(fromToken);
    const toTokenType = await this.detectChainTypeFromAddress(toToken);

    if (!fromTokenType || !toTokenType) {
      throw new BadRequestException('Invalid token address format');
    }

    // Check if tokens are from the same chain type
    if (fromTokenType !== toTokenType) {
      throw new BadRequestException(
        `Token chain types do not match: ${fromTokenType} and ${toTokenType}`
      );
    }
  }

  async resolveChains(
    fromToken: string,
    toToken: string,
    fromChain?: number,
    toChain?: number,
  ): Promise<{
    fromChainType: ChainType;
    fromChainId: number;
    toChainType: ChainType;
    toChainId: number;
  }> {
    // Validate tokens first
    await this.validateTokens(fromToken, toToken);

    // Detect chain type from token address
    const chainType = await this.detectChainTypeFromAddress(fromToken);
    if (!chainType) {
      throw new BadRequestException('Could not detect chain type from token address');
    }

    // If chains are provided, validate them
    if (fromChain && toChain) {
      // Validate chain IDs based on chain type
      this.validateChainIds(chainType, fromChain, toChain);
      return {
        fromChainType: chainType,
        fromChainId: fromChain,
        toChainType: chainType,
        toChainId: toChain,
      };
    }

    // If no chains provided, use default chain for the detected type
    const defaultChainId = this.getDefaultChainId(chainType);
    return {
      fromChainType: chainType,
      fromChainId: defaultChainId,
      toChainType: chainType,
      toChainId: defaultChainId,
    };
  }

  private validateChainIds(chainType: ChainType, fromChain: number, toChain: number): void {
    const validChainIds = this.getValidChainIds(chainType);
    
    if (!validChainIds.includes(fromChain)) {
      throw new BadRequestException(
        `Invalid fromChain ID ${fromChain} for chain type ${chainType}`
      );
    }
    
    if (!validChainIds.includes(toChain)) {
      throw new BadRequestException(
        `Invalid toChain ID ${toChain} for chain type ${chainType}`
      );
    }
  }

  private getValidChainIds(chainType: ChainType): number[] {
    switch (chainType) {
      case ChainType.EVM:
        return [
          this.configService.get<number>('ETH_CHAIN_ID'),
          this.configService.get<number>('BSC_CHAIN_ID'),
          this.configService.get<number>('BASE_CHAIN_ID'),
        ];
      case ChainType.SOLANA:
        return [this.configService.get<number>('SOLANA_CHAIN_ID')];
      case ChainType.MOVE:
        return [
          this.configService.get<number>('SUI_CHAIN_ID'),
          this.configService.get<number>('APTOS_CHAIN_ID'),
        ];
      default:
        throw new BadRequestException(`Unsupported chain type: ${chainType}`);
    }
  }

  private getDefaultChainId(chainType: ChainType): number {
    switch (chainType) {
      case ChainType.EVM:
        return this.configService.get<number>('ETH_CHAIN_ID');
      case ChainType.SOLANA:
        return this.configService.get<number>('SOLANA_CHAIN_ID');
      case ChainType.MOVE:
        return this.configService.get<number>('SUI_CHAIN_ID'); // Default to Sui for Move chains
      default:
        throw new BadRequestException(`Unsupported chain type: ${chainType}`);
    }
  }
} 