import { IsEmail, IsString, MinLength, IsOptional, IsEnum } from 'class-validator';
import { Platform } from '../wallet/entities/wallet.entity';

export enum AuthMethod {
  PASSWORD = 'PASSWORD',
  TELEGRAM = 'TELEGRAM',
  WEB3 = 'WEB3',
  GOOGLE = 'GOOGLE'
}

export class LoginDto {
  @IsEmail()
  email: string;

  @IsString()
  password: string;
}

export class RegisterDto {
  @IsString()
  name: string;

  @IsEmail()
  email: string;

  @IsString()
  password: string;

  @IsEnum(Platform)
  platform: Platform;
}

export class TelegramAuthDto {
  @IsString()
  telegramId: string;

  @IsString()
  name: string;

  @IsEmail()
  @IsOptional()
  email?: string;
}

export class Web3AuthDto {
  @IsString()
  walletAddress: string;

  @IsString()
  signature: string;

  @IsString()
  message: string;

  @IsString()
  @IsOptional()
  name?: string;

  @IsEmail()
  @IsOptional()
  email?: string;
}

export class GoogleAuthDto {
  @IsString()
  googleId: string;

  @IsString()
  name: string;

  @IsEmail()
  email: string;
}

export class ClientAuthDto {
  @IsEnum(Platform)
  platform: Platform;

  @IsString()
  clientId: string;

  @IsString()
  @MinLength(2)
  name: string;

  @IsEmail()
  @IsOptional()
  email?: string;
}

export class LoginOrRegisterDto {
  @IsEnum(Platform)
  platform: Platform;

  @IsEmail()
  @IsOptional()
  email?: string;

  @IsString()
  @MinLength(6)
  @IsOptional()
  password?: string;

  @IsString()
  @MinLength(2)
  name: string;

  @IsString()
  @IsOptional()
  clientId?: string;
}

export interface JwtPayload {
  sub: string;
  email: string;
  platform: Platform;
  authMethod: AuthMethod;
} 