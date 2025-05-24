import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ChainProviderService } from './chain-provider.service';
import { ChainProvider } from '../entities/chain-provider.entity';
import { ChainService } from './chain.service';
import { Chain } from '../entities/chain.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([ChainProvider, Chain])
  ],
  providers: [ChainProviderService, ChainService],
  exports: [ChainProviderService],
})
export class ChainProviderModule {} 