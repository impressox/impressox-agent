import { Injectable, NotFoundException, BadRequestException, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Wallet, ChainType, Platform } from './entities/wallet.entity';
import { EncryptionService } from './encryption.service';
import { ethers } from 'ethers';
import { UserService } from '../user/user.service';
import { Keypair } from '@solana/web3.js';
import { WalletStrategyFactory } from './strategies/wallet-strategy.factory';
import { User } from '../auth/entities/user.entity';

@Injectable()
export class WalletService {
  private readonly logger = new Logger(WalletService.name);

  constructor(
    @InjectRepository(Wallet)
    private readonly walletRepository: Repository<Wallet>,
    @InjectRepository(User)
    private readonly userRepository: Repository<User>,
    private readonly encryptionService: EncryptionService,
    private readonly userService: UserService,
    private readonly walletStrategyFactory: WalletStrategyFactory,
  ) {}

  async createWallet(userId: string, chainType: ChainType, chainId: number): Promise<Wallet> {
    const user = await this.userService.findById(userId);
    if (!user) {
      throw new NotFoundException('User not found');
    }

    const strategy = this.walletStrategyFactory.getStrategy(chainType);
    const { address, privateKey, mnemonic } = await strategy.generateWallet();

    const walletEntity = this.walletRepository.create({
      userId,
      chainType,
      chainId,
      address,
      encryptedPrivateKey: this.encryptionService.encrypt(privateKey),
      encryptedMnemonic: mnemonic ? this.encryptionService.encrypt(mnemonic) : null,
      isActive: true,
      platform: user.platform
    });

    return this.walletRepository.save(walletEntity);
  }

  async getWallet(userId: string, chainType: ChainType, chainId: number): Promise<Wallet | null> {
    return this.walletRepository.findOne({
      where: { userId, chainType, chainId }
    });
  }

  async getWallets(userId: string): Promise<Wallet[]> {
    return this.walletRepository.find({
      where: { userId },
      order: { createdAt: 'DESC' }
    });
  }

  async getDecryptedPrivateKey(walletId: string, userId: string): Promise<string> {
    const wallet = await this.walletRepository.findOne({
      where: { id: walletId, userId }
    });

    if (!wallet) {
      throw new NotFoundException('Wallet not found');
    }

    return this.encryptionService.decrypt(wallet.encryptedPrivateKey);
  }

  async getDecryptedMnemonic(walletId: string, userId: string): Promise<string | null> {
    const wallet = await this.walletRepository.findOne({
      where: { id: walletId, userId }
    });

    if (!wallet || !wallet.encryptedMnemonic) {
      return null;
    }

    return this.encryptionService.decrypt(wallet.encryptedMnemonic);
  }

  async deactivateWallet(walletId: string, userId: string): Promise<void> {
    const wallet = await this.walletRepository.findOne({
      where: { id: walletId, userId }
    });

    if (!wallet) {
      throw new NotFoundException('Wallet not found');
    }

    wallet.isActive = false;
    await this.walletRepository.save(wallet);
  }

  async getUserByWalletAddress(walletAddress: string): Promise<User> {
    const wallet = await this.walletRepository.findOne({
      where: { address: walletAddress },
      relations: ['user'],
    });

    if (!wallet || !wallet.user) {
      throw new NotFoundException('User not found for wallet address');
    }

    return wallet.user;
  }

  async getWalletByAddress(walletAddress: string): Promise<Wallet> {
    const wallet = await this.walletRepository.findOne({
      where: { address: walletAddress },
    });

    if (!wallet) {
      throw new NotFoundException('Wallet not found');
    }

    return wallet;
  }

  async getUserById(userId: string): Promise<User> {
    const user = await this.userRepository.findOne({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('User not found');
    }

    return user;
  }

  async getWalletByUserIdAndPlatform(
    userId: string,
    platform: Platform,
    chainType: ChainType,
    chainId: number
  ): Promise<Wallet | null> {
    return this.walletRepository.findOne({
      where: { 
        userId,
        platform,
        chainType,
        chainId
      }
    });
  }
} 