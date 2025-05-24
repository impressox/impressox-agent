import { Controller, Get, Post, Delete, Body, Param, UseGuards, Request } from '@nestjs/common';
import { WalletService } from './wallet.service';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { CreateWalletDto } from './dto/create-wallet.dto';
import { ChainType } from './entities/wallet.entity';

@Controller('wallets')
@UseGuards(JwtAuthGuard)
export class WalletController {
  constructor(private readonly walletService: WalletService) {}

  @Post()
  async createWallet(@Request() req, @Body() createWalletDto: CreateWalletDto) {
    return this.walletService.createWallet(
      req.user.id,
      createWalletDto.chainType,
      createWalletDto.chainId,
    );
  }

  @Get()
  async getWallets(@Request() req) {
    return this.walletService.getWallets(req.user.id);
  }

  @Get(':chainType/:chainId')
  async getWallet(
    @Request() req,
    @Param('chainType') chainType: ChainType,
    @Param('chainId') chainId: number
  ) {
    return this.walletService.getWallet(req.user.id, chainType, chainId);
  }

  @Delete(':id')
  async deactivateWallet(@Request() req, @Param('id') walletId: string) {
    await this.walletService.deactivateWallet(walletId, req.user.id);
    return { message: 'Wallet deactivated successfully' };
  }
} 