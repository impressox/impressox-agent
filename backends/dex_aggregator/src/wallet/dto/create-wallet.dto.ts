import { IsEnum, IsNumber, IsNotEmpty } from 'class-validator';
import { ChainType } from '../entities/wallet.entity';

export class CreateWalletDto {
  @IsEnum(ChainType)
  @IsNotEmpty()
  chainType: ChainType;

  @IsNumber()
  @IsNotEmpty()
  chainId: number;
} 