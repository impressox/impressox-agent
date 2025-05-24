import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Token } from './entities/token.entity';
import { ChainProviderService } from '../swap/services/chain-provider.service';
import { ConfigService } from '@nestjs/config';
import { ethers } from 'ethers';
import { ChainType } from '../wallet/entities/wallet.entity';

@Injectable()
export class TokenService {
  private readonly defaultFee: number;

  constructor(
    @InjectRepository(Token)
    private readonly tokenRepository: Repository<Token>,
    private readonly chainProviderService: ChainProviderService,
    private readonly configService: ConfigService,
  ) {
    this.defaultFee = parseFloat(this.configService.get('DEFAULT_SWAP_FEE', '0.5'));
  }

  async getToken(address: string, chainType: ChainType, chainId: number): Promise<Token | null> {
    return this.tokenRepository.findOne({
      where: { address, chainType, chainId }
    });
  }

  async getTokenFee(address: string, chainType: ChainType, chainId: number): Promise<number> {
    const token = await this.getToken(address, chainType, chainId);
    return token?.fee ?? this.defaultFee;
  }

  async createToken(tokenData: Partial<Token>): Promise<Token> {
    const token = this.tokenRepository.create(tokenData);
    return this.tokenRepository.save(token);
  }

  async updateToken(id: number, tokenData: Partial<Token>): Promise<Token> {
    await this.tokenRepository.update(id, tokenData);
    return this.tokenRepository.findOne({ where: { id } });
  }

  async deactivateToken(id: number): Promise<void> {
    await this.tokenRepository.update(id, { isActive: false });
  }

  async getTokenDecimals(address: string, chainId: number): Promise<number> {
    const provider = await this.chainProviderService.getProvider(chainId, ChainType.EVM);
    if (!provider) {
      throw new Error(`No provider found for chain ID ${chainId}`);
    }

    const ethersProvider = provider.getUnderlyingProvider();
    const tokenContract = new ethers.Contract(
      address,
      ['function decimals() view returns (uint8)'],
      ethersProvider
    );

    try {
      return await tokenContract.decimals();
    } catch (error) {
      throw new Error(`Failed to get token decimals: ${error.message}`);
    }
  }
} 