import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { WalletService } from './wallet.service';
import { WalletController } from './wallet.controller';
import { Wallet } from './entities/wallet.entity';
import { User } from '../user/entities/user.entity';
import { EncryptionService } from './encryption.service';
import { UserModule } from '../user/user.module';
import { WalletStrategyFactory } from './strategies/wallet-strategy.factory';

@Module({
  imports: [
    TypeOrmModule.forFeature([Wallet, User]),
    UserModule
  ],
  controllers: [WalletController],
  providers: [WalletService, EncryptionService, WalletStrategyFactory],
  exports: [WalletService]
})
export class WalletModule {} 