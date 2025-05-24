import { Injectable, BadRequestException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ChainProvider } from '../entities/chain-provider.entity';
import { ChainType } from '../../wallet/entities/wallet.entity';
import { DexProvider } from '../entities/provider.enum';
import { ethers } from 'ethers';
import { ConfigService } from '@nestjs/config';
import { ChainService } from './chain.service';
import { AptosClient } from 'aptos';
import { Connection, PublicKey } from '@solana/web3.js';

import { SuiClient } from '@mysten/sui/client';

interface IProvider {
  getCode(address: string): Promise<string>;
  getRouterContract(address: string, abi: any[]): Promise<any>;
  getUnderlyingProvider(): any;
}

class EVMProvider implements IProvider {
  private provider: ethers.JsonRpcProvider;

  constructor(rpcUrl: string) {
    this.provider = new ethers.JsonRpcProvider(rpcUrl);
  }

  async getCode(address: string): Promise<string> {
    return this.provider.getCode(address);
  }

  getUnderlyingProvider(): ethers.JsonRpcProvider {
    return this.provider;
  }

  async getRouterContract(address: string, abi: any[]): Promise<ethers.Contract | null> {
    if (!address || !abi) return null;
    return new ethers.Contract(address, abi, this.provider);
  }
}

class MoveProvider implements IProvider {
  private client: AptosClient | SuiClient;

  constructor(rpcUrl: string, isAptos: boolean) {
    this.client = isAptos ? 
      new AptosClient(rpcUrl) : 
      new SuiClient({ url: rpcUrl });
  }

  async getCode(address: string): Promise<string> {
    if (this.client instanceof AptosClient) {
      const resource = await this.client.getAccountResource(address, '0x1::coin::CoinInfo');
      return resource ? '0x1' : '0x';
    } else {
      try {
        const object = await (this.client as SuiClient).getObject({
          id: address,
          options: { showContent: true }
        });
        return object && object.data ? '0x1' : '0x';
      } catch (error) {
        return '0x';
      }
    }
  }

  getUnderlyingProvider(): AptosClient | SuiClient {
    return this.client;
  }

  async getRouterContract(address: string, abi: any[]): Promise<{ client: AptosClient | SuiClient; address: string; abi: any[] } | null> {
    if (!address || !abi) return null;
    return {
      client: this.client,
      address,
      abi
    };
  }
}

class SolanaProvider implements IProvider {
  private connection: Connection;

  constructor(rpcUrl: string) {
    this.connection = new Connection(rpcUrl);
  }

  async getCode(address: string): Promise<string> {
    try {
      const publicKey = new PublicKey(address);
      const accountInfo = await this.connection.getAccountInfo(publicKey);
      return accountInfo && accountInfo.data ? '0x1' : '0x';
    } catch {
      return '0x';
    }
  }

  getUnderlyingProvider(): Connection {
    return this.connection;
  }

  async getRouterContract(address: string, abi: any[]): Promise<{ connection: Connection; address: string; abi: any[] } | null> {
    if (!address || !abi) return null;
    return {
      connection: this.connection,
      address,
      abi
    };
  }
}

class CairoProvider implements IProvider {
  private provider: ethers.JsonRpcProvider;

  constructor(rpcUrl: string) {
    this.provider = new ethers.JsonRpcProvider(rpcUrl);
  }

  async getCode(address: string): Promise<string> {
    try {
      const code = await this.provider.getCode(address);
      if (code === '0x') return '0x';

      const classHash = await this.provider.getStorage(address, '0x0');
      return classHash !== '0x0' ? '0x1' : '0x';
    } catch {
      return '0x';
    }
  }

  getUnderlyingProvider(): ethers.JsonRpcProvider {
    return this.provider;
  }

  async getRouterContract(address: string, abi: any[]): Promise<ethers.Contract | null> {
    if (!address || !abi) return null;
    return new ethers.Contract(address, abi, this.provider);
  }
}

class ProviderFactory {
  private static providers: Map<string, IProvider> = new Map();

  static createProvider(chainType: ChainType, rpcUrl: string, chainId: number): IProvider {
    const key = `${chainType}-${chainId}`;
    
    if (this.providers.has(key)) {
      return this.providers.get(key);
    }

    let provider: IProvider;

    switch (chainType) {
      case ChainType.EVM:
        provider = new EVMProvider(rpcUrl);
        break;
      case ChainType.MOVE:
        provider = new MoveProvider(rpcUrl, chainId === 1); // Assuming 1 is Aptos chain ID
        break;
      case ChainType.SOLANA:
        provider = new SolanaProvider(rpcUrl);
        break;
      case ChainType.CAIRO:
        provider = new CairoProvider(rpcUrl);
        break;
      default:
        throw new BadRequestException(`Unsupported chain type: ${chainType}`);
    }

    this.providers.set(key, provider);
    return provider;
  }
}

@Injectable()
export class ChainProviderService {
  constructor(
    @InjectRepository(ChainProvider)
    private readonly chainProviderRepository: Repository<ChainProvider>,
    private readonly chainService: ChainService,
    private readonly configService: ConfigService,
  ) {}

  async getProvider(chainId: number, chainType: ChainType): Promise<IProvider> {
    const provider = await this.chainProviderRepository.findOne({
      where: { chainId, chainType, isActive: true },
      order: { priority: 'DESC' }
    });

    if (!provider || !provider.rpcUrl) {
      throw new BadRequestException(`No RPC URL configured for chain ID ${chainId}`);
    }

    return ProviderFactory.createProvider(chainType, provider.rpcUrl, chainId);
  }

  async getProvidersByChainId(chainId: number): Promise<ChainProvider[]> {
    await this.chainService.getChain(chainId);

    return this.chainProviderRepository.find({
      where: { 
        chainId,
        isActive: true 
      },
      order: { 
        priority: 'DESC'
      },
      relations: ['chain']
    });
  }

  async getProviderConfig(
    chainId: number,
    provider: DexProvider
  ): Promise<ChainProvider | null> {
    return this.chainProviderRepository.findOne({
      where: {
        chainId,
        provider,
        isActive: true
      },
      relations: ['chain']
    });
  }

  async resolveTokenChain(tokenAddress: string): Promise<{ chainType: ChainType; chainId: number }> {
    const supportedChains = await this.chainService.getActiveChains();
    
    for (const chain of supportedChains) {
      try {
        const chainProvider = await this.chainProviderRepository.findOne({
          where: { chainId: chain.chainId, isActive: true },
          order: { priority: 'DESC' }
        });

        if (!chainProvider) continue;

        const provider = await this.getProvider(chain.chainId, chainProvider.chainType);
        const code = await provider.getCode(tokenAddress);

        if (code !== '0x') {
          return {
            chainType: chainProvider.chainType,
            chainId: chain.chainId
          };
        }
      } catch (error) {
        continue;
      }
    }
    
    throw new BadRequestException(`Token ${tokenAddress} not found on any supported chain`);
  }

  async validateChainSupport(chainId: number, provider: DexProvider): Promise<void> {
    const providerConfig = await this.getProviderConfig(chainId, provider);
    if (!providerConfig) {
      throw new BadRequestException(
        `Provider ${provider} does not support chain ID ${chainId}`
      );
    }
  }

  async getRouterContract(chainId: number, provider: DexProvider): Promise<any> {
    const providerConfig = await this.getProviderConfig(chainId, provider);
    if (!providerConfig || !providerConfig.routerAddress || !providerConfig.routerAbi) {
      return null;
    }

    const chainProvider = await this.getProvider(chainId, providerConfig.chainType);
    return chainProvider.getRouterContract(providerConfig.routerAddress, providerConfig.routerAbi);
  }

  async createProvider(providerData: Partial<ChainProvider>): Promise<ChainProvider> {
    await this.chainService.getChain(providerData.chainId);
    
    // Validate router address and ABI if provided
    if (providerData.routerAddress && !providerData.routerAbi) {
      throw new BadRequestException('Router ABI is required when router address is provided');
    }

    const provider = this.chainProviderRepository.create(providerData);
    return this.chainProviderRepository.save(provider);
  }

  async updateProvider(id: number, providerData: Partial<ChainProvider>): Promise<ChainProvider> {
    if (providerData.chainId) {
      await this.chainService.getChain(providerData.chainId);
    }
    
    // Validate router address and ABI if provided
    if (providerData.routerAddress && !providerData.routerAbi) {
      throw new BadRequestException('Router ABI is required when router address is provided');
    }
    
    await this.chainProviderRepository.update(id, providerData);
    return this.chainProviderRepository.findOne({ 
      where: { id },
      relations: ['chain']
    });
  }

  async deactivateProvider(id: number): Promise<void> {
    await this.chainProviderRepository.update(id, { isActive: false });
  }
} 