import { Controller, Post, Body, UseGuards, Req, UnauthorizedException, Get, Param, Query, BadRequestException } from '@nestjs/common';
import { SwapService } from './swap.service';
import { SwapRequestDto } from './dto/swap-request.dto';
import { QuoteResponse } from './strategies/provider-strategy.interface';
import { AuthGuard } from '@nestjs/passport';
import { Request } from 'express';
import { WalletService } from '../wallet/wallet.service';
import { User } from '../auth/entities/user.entity';
import { Logger } from '@nestjs/common';
import { GetQuoteRequest } from './dto/get-quote-request.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { ChainType, Platform } from '../wallet/entities/wallet.entity';
import { ChainProviderService } from './services/chain-provider.service';

@Controller('swap')
export class SwapController {
  private readonly logger = new Logger(SwapController.name);

  constructor(
    private readonly swapService: SwapService,
    private readonly walletService: WalletService,
    private readonly chainProviderService: ChainProviderService,
  ) {}

  @Post('quote')
  async getQuote(@Body() request: GetQuoteRequest, @Req() req: Request & { user?: User }): Promise<QuoteResponse> {
    const userId = req.user?.id;
    return this.swapService.processSwapRequest(request, userId);
  }

  @Post('execute')
  async executeSwap(@Body() request: SwapRequestDto, @Req() req: Request & { user?: User }): Promise<{ txHash: string }> {
    const userId = req.user?.id;
    const quote = await this.swapService.processSwapRequest(request, userId);

    // Resolve token chain
    const fromToken = request.fromToken || '0x0000000000000000000000000000000000000000';
    const chain = await this.chainProviderService.resolveTokenChain(fromToken);

    // Get wallet address
    let walletAddress: string;
    if (userId) {
      const wallet = await this.walletService.getWalletByUserIdAndPlatform(
        String(userId),
        request.platform as Platform,
        chain.chainType,
        chain.chainId
      );
      if (!wallet) {
        throw new BadRequestException(`No wallet found for chain ${chain.chainType} ${chain.chainId}`);
      }
      walletAddress = wallet.address;
    } else {
      if (!request.walletAddress) {
        throw new BadRequestException('Wallet address is required for unauthenticated requests');
      }
      walletAddress = request.walletAddress;
    }

    const txHash = await this.swapService.executeSwap(
      quote,
      walletAddress,
      chain.chainType,
      chain.chainId
    );

    return { txHash };
  }

  @UseGuards(JwtAuthGuard)
  @Post('quote-and-swap')
  async quoteAndSwap(@Body() request: SwapRequestDto, @Req() req: Request & { user: User }): Promise<{ quote: QuoteResponse; txHash: string }> {
    const userId = req.user.id;
    const quote = await this.swapService.processSwapRequest(request, userId);

    // Resolve token chain
    const fromToken = request.fromToken || '0x0000000000000000000000000000000000000000';
    const chain = await this.chainProviderService.resolveTokenChain(fromToken);

    // Get wallet address
    const wallet = await this.walletService.getWalletByUserIdAndPlatform(
      String(userId),
      request.platform as Platform,
      chain.chainType,
      chain.chainId
    );
    if (!wallet) {
      throw new BadRequestException(`No wallet found for chain ${chain.chainType} ${chain.chainId}`);
    }

    const txHash = await this.swapService.executeSwap(
      quote,
      wallet.address,
      chain.chainType,
      chain.chainId
    );

    return {
      quote,
      txHash,
    };
  }

  @Get('providers')
  async getProviders(@Query('chainId') chainId: number): Promise<any> {
    return this.chainProviderService.getProvidersByChainId(chainId);
  }
} 