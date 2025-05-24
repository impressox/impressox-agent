import { Injectable, BadRequestException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Chain } from '../entities/chain.entity';

@Injectable()
export class ChainService {
  constructor(
    @InjectRepository(Chain)
    private readonly chainRepository: Repository<Chain>,
  ) {}

  async getChain(chainId: number): Promise<Chain> {
    const chain = await this.chainRepository.findOne({
      where: { chainId, isActive: true }
    });

    if (!chain) {
      throw new BadRequestException(`No active chain found for chain ID ${chainId}`);
    }

    return chain;
  }

  async getActiveChains(): Promise<Chain[]> {
    return this.chainRepository.find({
      where: { isActive: true }
    });
  }

  async createChain(chainData: Partial<Chain>): Promise<Chain> {
    const chain = this.chainRepository.create(chainData);
    return this.chainRepository.save(chain);
  }

  async updateChain(id: number, chainData: Partial<Chain>): Promise<Chain> {
    await this.chainRepository.update(id, chainData);
    return this.chainRepository.findOne({ where: { id } });
  }

  async deactivateChain(id: number): Promise<void> {
    await this.chainRepository.update(id, { isActive: false });
  }
} 