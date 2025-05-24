import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Token } from './entities/token.entity';
import { TokenService } from './token.service';
import { ChainProviderModule } from '../swap/services/chain-provider.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([Token]),
    ChainProviderModule
  ],
  providers: [TokenService],
  exports: [TokenService],
})
export class TokenModule {} 