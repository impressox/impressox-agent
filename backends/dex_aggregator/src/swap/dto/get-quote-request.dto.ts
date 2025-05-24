import { IsString, IsNumber, IsOptional, IsEnum, IsNotEmpty } from 'class-validator';
import { DexProvider } from '../entities/provider.enum';

export class GetQuoteRequest {
  @IsString()
  @IsNotEmpty()
  fromToken: string;

  @IsString()
  @IsNotEmpty()
  toToken: string;

  @IsString()
  @IsNotEmpty()
  amount: string;

  @IsEnum(DexProvider)
  provider: DexProvider;

  @IsString()
  platform: string;

  @IsString()
  @IsOptional()
  walletAddress?: string;

  @IsNumber()
  @IsOptional()
  slippage?: number;
} 