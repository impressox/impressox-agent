import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { OneInchStrategy } from './oneinch.strategy';
import { LifiStrategy } from './lifi.strategy';
import { AuthModule } from '../../auth/auth.module';
import { TokenModule } from '../../token/token.module';
import { ChainProviderModule } from '../services/chain-provider.module';

@Module({
  imports: [
    ConfigModule,
    AuthModule,
    TokenModule,
    ChainProviderModule
  ],
  providers: [
    OneInchStrategy,
    LifiStrategy
  ],
  exports: [OneInchStrategy, LifiStrategy],
})
export class StrategiesModule {} 