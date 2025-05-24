import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { TokenModule } from '../token/token.module';
import { SwapService } from './swap.service';
import { ChainProvider } from './entities/chain-provider.entity';
import { Chain } from './entities/chain.entity';
import { StrategiesModule } from './strategies/strategies.module';
import { SwapController } from './swap.controller';
import { AuthModule } from '../auth/auth.module';
import { WalletModule } from '../wallet/wallet.module';
import { ChainProviderService } from './services/chain-provider.service';
import { ChainService } from './services/chain.service';
import { TokenChainService } from './services/token-chain.service';
import { ChainProviderModule } from './services/chain-provider.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([ChainProvider, Chain]),
    TokenModule,
    StrategiesModule,
    AuthModule,
    WalletModule,
    ChainProviderModule
  ],
  controllers: [SwapController],
  providers: [
    SwapService,
    ChainProviderService,
    ChainService,
    TokenChainService
  ],
  exports: [SwapService],
})
export class SwapModule {} 